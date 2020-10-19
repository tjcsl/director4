# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

# pylint: disable=no-self-use,too-few-public-methods

import asyncio
import enum
import json
import logging
import time
import urllib
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import asyncssh
import websockets

from . import manager_interface, settings
from .root_shell import RootShellSession
from .util import run_default_executor

logger = logging.getLogger(__name__)


class ShellSSHListener:
    def __init__(self, bind_host: str, bind_port: int, server_host_keys: Iterable[str]) -> None:
        self.bind_host = bind_host
        self.bind_port = bind_port

        server_host_keys = list(server_host_keys)
        if not server_host_keys:
            raise ValueError("Server host keys must be passed")

        self.server_host_keys = server_host_keys

        self.servers: List[ShellSSHServer] = []

        self.sock_server: Optional[asyncio.base_events.Server] = None

    async def start(self) -> None:
        self.sock_server = await asyncssh.listen(
            host=self.bind_host,
            port=self.bind_port,
            server_host_keys=self.server_host_keys,
            server_factory=self.create_server,
            line_editor=True,
        )

    def close(self) -> None:
        assert self.sock_server is not None
        self.sock_server.close()

    async def wait_closed(self) -> None:
        assert self.sock_server is not None
        await self.sock_server.wait_closed()

    def create_server(self) -> "ShellSSHServer":
        return ShellSSHServer(self)


class ShellSSHServer(asyncssh.SSHServer):  # type: ignore
    def __init__(self, listener: ShellSSHListener) -> None:
        self.listener = listener
        self.conn: Optional[asyncssh.SSHClientConnection] = None

        # There's support here for a system where the username is specified in the format:
        # <username>/<site name>
        # The result is that it's possible to do things like "ssh user/site@host" and skip the
        # site selection page.
        # So here's what these variables mean:
        # self.raw_username is the original, unparsed username as received from the client.
        # self.username is the username to use to authenticate.
        # self.site_name is the part after the "/" if this format is used. Otherwise it is None.
        self.raw_username: Optional[str] = None
        self.username: Optional[str] = None
        self.site_name: Optional[str] = None

        self.sites: Optional[Dict[str, Tuple[int, str]]] = None

    def connection_made(self, conn: asyncssh.SSHClientConnection) -> None:
        # This is called when a connection opens.
        # Give the parent ShellSSHListener a reference to this object
        # so it can keep track of open connections.
        self.listener.servers.append(self)
        self.conn = conn

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc is not None:
            logger.error("Disconnected: %s: %s", exc.__class__.__name__, exc)

        if self in self.listener.servers:
            self.listener.servers.remove(self)

    def begin_auth(self, username: str) -> bool:
        # Record the usernane
        self.raw_username = username
        return True

    def password_auth_supported(self) -> bool:
        return True

    # AsyncSSH special-cases this method to allow it to be async
    async def validate_password(  # pylint: disable=invalid-overridden-method
        self, username: str, password: str,
    ) -> bool:
        if not username or username != self.raw_username:
            return False

        result = False

        self.username = username

        if username == "root":
            result = bool(password)
        else:
            # See the description of this format in __init__()
            if "/" in username:
                username, self.site_name = username.split("/", 1)
                self.username = username
            else:
                self.site_name = None

            result = await run_default_executor(self._check_password_sync, self.username, password)

        if result is not True:
            await asyncio.sleep(3)
            return False

        return True

    def _check_password_sync(self, username: str, password: str) -> bool:
        try:
            res = manager_interface.make_manager_request(
                "/shell-server/authenticate/",
                method="POST",
                data={"username": username, "password": password},
            )
        except (urllib.error.HTTPError, manager_interface.ManagerRequestError):
            return False
        else:
            self.sites = json.load(res)
            return True

    def session_requested(self) -> asyncssh.SSHServerSession:
        if self.username == "root":
            return RootShellSession()
        else:
            return ShellSSHServerSession(self)


class ShellSSHSessionState(enum.Enum):
    BEGIN = 0
    SELECT_SITE = 1
    PROXY = 2
    CLOSED = 3


class ShellSSHServerSession(asyncssh.SSHServerSession):  # type: ignore # pylint: disable=too-many-instance-attributes, line-too-long # noqa
    def __init__(self, server: ShellSSHServer) -> None:
        assert server.username is not None
        assert server.sites is not None

        self.server = server
        self.chan: Optional[asyncssh.SSHServerChannel] = None

        self.buffer = b""
        # This Event is fired whenever new data is made available on the buffer.
        # It's also fired when the connection is closed, so anything using this
        # should also check for that case.
        # It is never clear()ed by the firing code, so if you're wait()ing for it
        # you should immediately clear it
        self.buffer_update_event = asyncio.Event()

        self.websock: Optional[websockets.WebSocketClientProtocol] = None

        self.websock_send_lock = asyncio.Lock()

        self.pty_opened = False

        self.state: ShellSSHSessionState = ShellSSHSessionState.BEGIN

    # SSHServerSession API

    def exec_requested(self, command: str) -> bool:
        return False

    def subsystem_requested(self, subsystem: str) -> bool:
        return False

    def connection_made(self, chan: asyncssh.SSHServerChannel) -> None:
        self.chan = chan

    def connection_lost(self, exc: Optional[Exception]) -> None:
        if exc is not None:
            logger.error("Disconnected: %s: %s", exc.__class__.__name__, exc)

        self.close()

    def pty_requested(
        self,
        term_type: Optional[str],
        term_size: Tuple[int, int, int, int, int],
        term_modes: Dict[int, int],
    ) -> bool:
        self.pty_opened = True
        return True

    def shell_requested(self) -> bool:
        return True

    def session_started(self) -> None:
        if not self.pty_opened:
            # Terminal not requested
            self.write_stderr_bytes(b"You must request a TTY.\n")
            self.close(exit_status=1)
            return

        asyncio.ensure_future(self.setup_connection())

    def data_received(self, data: Union[str, bytes], datatype: Any) -> None:
        # We got some data from the server

        # Make sure it's bytes
        if isinstance(data, str):
            data = data.encode()

        # This should never happen, but let's check just to make sure
        if self.chan is None:
            return

        if self.state in {ShellSSHSessionState.BEGIN, ShellSSHSessionState.SELECT_SITE}:
            # We haven't switched to proxying mode yet. Add the data to a "buffer".
            self.buffer += data

            # Too much data, too soon! Abort.
            if len(self.buffer) > 1000:
                self.close(exit_status=1)

            # Signal that there's new data on the buffer.
            self.buffer_update_event.set()
        elif self.state == ShellSSHSessionState.PROXY:
            # We're in proxy mode! Write directly to the websocket.
            if self.websock is not None:
                asyncio.ensure_future(self.send_websock_data(data))

    def signal_received(self, signal: Any) -> None:
        pass

    def break_received(self, msec: int) -> bool:
        if self.state == ShellSSHSessionState.PROXY:
            self.data_received(b"\x03", 0)
            return True
        else:
            self.close()
            return False

    def eof_received(self) -> bool:
        if self.state == ShellSSHSessionState.PROXY:
            self.data_received(b"\x04", 0)
        else:
            self.close()

        return False

    def soft_eof_received(self) -> bool:
        return self.eof_received()

    def terminal_size_changed(
        self,
        width: int,
        height: int,
        pixwidth: Optional[int] = None,
        pixheight: Optional[int] = None,
    ) -> None:
        # Send the new size ASAP
        asyncio.ensure_future(self.send_new_tty_size())

    # Internal methods

    async def send_websock_data(self, data: bytes) -> None:
        """Sends the given data to self.websock, locking on self.websock_send_lock.

        Once proxy mode has been entered and self.websock has been set, this should
        be used to send all data to the underlying websocket, since it prevents race
        conditions that could result in data being sent out of order.

        """

        try:
            async with self.websock_send_lock:
                if self.websock is None:
                    return

                await self.websock.send(data)
        except websockets.WebSocketException:
            self.close()

    async def get_site_name(self) -> Optional[str]:
        assert self.chan is not None

        if not self.server.sites:
            self.write_stderr_bytes(b"You have no sites to connect to.\r\n")

            return None

        if self.server.site_name:
            if self.server.site_name not in self.server.sites:
                self.write_stderr_bytes(
                    b"The requested site does not exist or you do not have access to it.\r\n"
                )

                return None

            return self.server.site_name

        data = (
            "Please select a site to connect to:\r\n- "
            + "\r\n- ".join(self.server.sites.keys())
            + "\r\nSite name: "
        )

        self.write_bytes(data.encode())

        self.chan.set_line_mode(True)
        self.chan.set_echo(True)

        self.state = ShellSSHSessionState.SELECT_SITE

        while True:
            # Wait for new data on the buffer
            await self.buffer_update_event.wait()
            self.buffer_update_event.clear()

            # close() signals on self.buffer_update_event.
            # Did the connection just get closed?
            if self.chan is None:
                return None

            index = self.buffer.find(b"\n")
            if index < 0:
                continue

            raw_line, self.buffer = self.buffer[:index], self.buffer[index + 1:]

            line = raw_line.decode("latin-1")

            if line in self.server.sites:
                return line
            else:
                self.write_bytes(b"Site name: ")

    async def setup_connection(self) -> None:
        assert self.chan is not None
        assert self.server.sites is not None

        site_name = await self.get_site_name()
        if not site_name:
            self.close()
            return

        self.write_bytes(b"Connecting to site '" + site_name.encode() + b"'\r\n")
        site_id, token = self.server.sites[site_name]

        await self.connect_websock(site_id, site_name, token)
        if self.websock is None:
            return

        await self.send_new_tty_size()

        self.chan.set_line_mode(False)
        self.chan.set_echo(False)
        self.chan.set_encoding(None)
        self.chan._editor = None  # pylint: disable=protected-access

        await self.websock_mainloop()

    def write_bytes(self, data: bytes) -> None:
        assert self.chan is not None

        if self.chan.get_encoding()[0] is None:
            self.chan.write(data)
        else:
            self.chan.write(data.decode("latin-1"))

    def write_stderr_bytes(self, data: bytes) -> None:
        assert self.chan is not None

        if self.chan.get_encoding()[0] is None:
            self.chan.write_stderr(data)
        else:
            self.chan.write_stderr(data.decode("latin-1"))

    async def connect_websock(self, site_id: int, site_name: str, token: str) -> None:
        websock = None

        # Copy the manager's strategy
        appserver_num = hash(str(site_id) + site_name) % len(settings.APPSERVER_WS_HOSTS)

        orig_appserver_num = appserver_num

        while True:
            host = settings.APPSERVER_WS_HOSTS[appserver_num]
            try:
                websock = await asyncio.wait_for(
                    websockets.connect(
                        "ws{}://{}/ws/shell-server/{}/ssh-shell/".format(
                            "s" if settings.APPSERVER_SSL_CONTEXT is not None else "",
                            host,
                            site_id,
                        ),
                        ping_interval=30,
                        ping_timeout=10,
                        close_timeout=10,
                        ssl=settings.APPSERVER_SSL_CONTEXT,
                    ),
                    timeout=2,
                )
                break
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake) as ex:
                logging.error("Error connecting to appserver %d: %s", appserver_num, ex)

                appserver_num = (appserver_num + 1) % len(settings.APPSERVER_WS_HOSTS)

                if appserver_num == orig_appserver_num:
                    # We've come full circle; none are reachable
                    self.close()
                    return

        try:
            await websock.send(token)

            frame = await websock.recv()
            if isinstance(frame, str):
                try:
                    msg = json.loads(frame)
                except json.JSONDecodeError:
                    self.close()
                    return
                else:
                    if not msg.get("connected"):
                        self.close()
                        return
            else:
                self.close()
                return

            # Flush the buffer through to the socket
            buf, self.buffer = self.buffer, b""
            await websock.send(buf)
            # Now switch to proxy mode
            self.websock = websock
            self.state = ShellSSHSessionState.PROXY
            # And flush the buffer again in case something got through
            await self.send_websock_data(buf)

            if self.websock is None:
                self.write_stderr_bytes(b"Internal connection error; please try again later\r\n")
                self.close(exit_status=1)
            else:
                await self.send_new_tty_size()
        except websockets.WebSocketException:
            self.close()

    async def websock_mainloop(self) -> None:
        assert self.websock is not None
        assert self.chan is not None

        last_heartbeat_time = time.time()

        while True:
            frame: Union[str, bytes, None]

            try:
                frame = await asyncio.wait_for(self.websock.recv(), 35)
            except asyncio.TimeoutError:
                frame = None
            except websockets.WebSocketException:
                self.close()
                break

            if time.time() - last_heartbeat_time >= 30:
                try:
                    await self.websock.send(json.dumps({"heartbeat": 1}))
                except websockets.WebSocketException:
                    self.close()
                    break
                else:
                    last_heartbeat_time = time.time()

            if isinstance(frame, bytes):
                # First byte indicates stdout/stderr
                if frame[0] == 0:
                    # stdout
                    await run_default_executor(self.chan.write, frame[1:])
                else:
                    # stderr
                    await run_default_executor(self.chan.write_stderr, frame[1:])

    async def send_new_tty_size(self) -> None:
        if self.websock is not None and self.chan is not None and self.pty_opened:
            width, height = self.chan.get_terminal_size()[:2]
            try:
                await self.websock.send(json.dumps({"size": [height, width]}))
            except websockets.WebSocketException:
                pass

    def close(self, *, exit_status: Optional[int] = None) -> None:
        self.state = ShellSSHSessionState.CLOSED

        if self.chan is not None and not self.chan.is_closing():
            if exit_status is not None:
                self.chan.exit(exit_status)
            else:
                self.chan.close()

            self.chan = None

        if self.websock is not None:
            asyncio.ensure_future(self.websock.close())
            self.websock = None

        # Unblock anything waiting for a buffer update.
        self.buffer_update_event.set()
