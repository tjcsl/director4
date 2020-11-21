# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import socket
import time
from typing import Any, Dict, List, Optional

from docker.client import DockerClient
from docker.errors import APIError, ImageNotFound, NotFound
from docker.models.containers import Container
from docker.types import Mount

from . import settings
from .docker import containers
from .docker.shared import gen_director_container_env
from .utils import run_in_executor


class TerminalContainer:  # pylint: disable=too-many-instance-attributes
    """Class for starting a specific site's terminal container.

    WARNING: Whenever you see operations on the raw socket (self.socket._sock), there's probably
    a reason we don't do them on self.socket, even if it isn't explicitly documented.
    So be careful.

    """

    def __init__(self, client: DockerClient, site_id: int, site_data: Dict[str, Any]) -> None:
        self.client = client
        self.site_id = site_id
        self.site_data = site_data

        self.container_name = "site_{:04d}_terminal".format(site_id)

        self.container: Optional[Container] = None

        self.exec_id: Optional[str] = None

        self.socket: Optional[socket.SocketIO] = None

        self.reader: Optional[asyncio.StreamReader] = None
        self.writer: Optional[asyncio.StreamWriter] = None

        self.closed = False

    async def start(self, *, command: Optional[List[str]] = None) -> None:
        await self._start_attach(command)

        assert self.socket is not None
        # The default timeout is 60 seconds, which is way too low
        # 1 day is probably overkill, but why not?
        self.socket._sock.settimeout(24 * 60 * 60)  # pylint: disable=protected-access

        # We have to do this here because the executor doesn't have a running event loop
        self.reader, self.writer = await asyncio.open_connection(
            sock=self.socket._sock  # pylint: disable=protected-access
        )

        await self.resize(24, 80)

        await self.heartbeat()

    def _launch_container(self, run_params: Dict[str, Any]) -> None:
        while True:
            try:
                self.container = containers.get_or_create_container(
                    self.client, self.container_name, run_params=run_params,
                )
            except APIError as ex:
                msg = str(ex).lower()
                if "conflict" in msg and "already in use" in msg:
                    # The container is in the process of being launched; sleep and try again
                    time.sleep(2)
                else:
                    raise
            else:
                break

    @run_in_executor(None)
    def _start_attach(self, command: Optional[List[str]]) -> None:
        """Internal function that runs in an executor and performs all the long-running synchronous
        operations needed to create the container (if necessary) and attach to it."""
        run_params = containers.gen_director_container_params(
            self.client, self.site_id, self.site_data
        )

        # Allows for the use of a C program to perform keepalive instead of using `sh`
        # Using a C program allows greater control of low-level interactions
        # (e.g. niceness, disk I/O priority).
        if settings.TERMINAL_KEEPALIVE_PROGRAM_PATH is not None:
            keepalive_command = [
                "/terminal-keepalive",
                str(settings.SITE_TERMINAL_KEEPALIVE_TIMEOUT),
            ]
            run_params["mounts"].append(
                Mount(
                    "/terminal-keepalive",
                    settings.TERMINAL_KEEPALIVE_PROGRAM_PATH,
                    type="bind",
                    read_only=True,
                )
            )
        else:
            keepalive_command = [
                "sh",
                "-c",
                'while timeout "$1" head -n 1 &>/dev/null; do true; done',
                "sh",
                str(settings.SITE_TERMINAL_KEEPALIVE_TIMEOUT),
            ]

        run_params.update(
            {
                "command": keepalive_command,
                "read_only": True,
                "auto_remove": True,
                "stdin_open": True,
            }
        )

        self._launch_container(run_params)

        assert self.container is not None

        orig_image_name = run_params["image"]

        if "/" in orig_image_name:
            # One of these formats:
            # - hostname/image
            # - hostname:port/image
            # - hostname/image:tag
            # - hostname:port/image:tag

            # Split out the hostname/port combo if present
            server, image_name_with_tag = orig_image_name.split("/")

            if ":" in image_name_with_tag:
                # It has a tag name
                image_name, tag_name = image_name_with_tag.split(":")
                image_name = server + "/" + image_name
            else:
                # No tag name
                image_name = orig_image_name
                tag_name = "latest"

            # This format means it's from our custom registry. Unconditionally pull so we always get
            # the latest built image.
            image = self.client.images.pull(image_name, tag_name)
        else:
            # One of these formats:
            # - image
            # - image:tag

            if ":" in orig_image_name:
                image_name, tag_name = orig_image_name.split(":")
            else:
                image_name = orig_image_name
                tag_name = "latest"

            # This format means it's from DockerHub. To avoid hitting the rate limit, only pull if
            # it's not present.
            try:
                image = self.client.images.get(orig_image_name)
            except ImageNotFound:
                image = self.client.images.pull(image_name, tag_name)

        if self.container.image.id != image.id:
            self.container.stop()
            try:
                self.container.wait()
            except NotFound:
                pass

            self._launch_container(run_params)

        env = gen_director_container_env(self.client, self.site_id, self.site_data)

        # See docs/UMASK.md before changing the umask setup
        if command is None:
            args = [
                "sh",
                "-c",
                'umask "$1"; if [ -x /bin/bash ]; then exec bash; fi; exec sh',
                "sh",
                oct(settings.SITE_UMASK)[2:],
            ]
        else:
            args = [
                "sh",
                "-c",
                'umask "$1"; shift; exec "$@"',
                "sh",
                oct(settings.SITE_UMASK)[2:],
                *command,
            ]

        self.exec_id = self.client.api.exec_create(
            self.container.id,
            args,
            stdin=True,
            stdout=True,
            stderr=True,
            tty=True,
            privileged=False,
            workdir="/site",
            environment=env,
            user="root",
        )["Id"]

        self.socket = self.client.api.exec_start(
            self.exec_id, tty=True, detach=False, demux=False, socket=True,
        )

    @run_in_executor(None)
    def heartbeat(self) -> None:
        assert self.container is not None

        with self.container.attach_socket(params={"stdin": 1, "stream": 1}, ws=False) as sock:
            # We have to pry into the internals of docker-py a little. There is no known way around
            # this.
            # Sources:
            # https://stackoverflow.com/q/26843625
            # https://github.com/docker/docker-py/pull/239#issuecomment-246149032

            sock._sock.send(b"\n")  # pylint: disable=protected-access

    async def read(self, bufsize: int) -> bytes:
        if self.reader is None or self.closed:
            return b""

        return await self.reader.read(bufsize)

    async def write(self, data: bytes) -> None:
        assert self.writer is not None
        self.writer.write(data)
        await self.writer.drain()

    @run_in_executor(None)
    def resize(self, rows: int, cols: int) -> None:
        assert self.exec_id is not None

        self.client.api.exec_resize(self.exec_id, height=rows, width=cols)

    @run_in_executor(None)
    def close(self) -> None:
        if self.socket is not None and not self.closed:
            # It's not enough to close the socket; to force-interrupt read()s we need to shut
            # it down first.
            self.socket._sock.shutdown(socket.SHUT_RDWR)  # pylint: disable=protected-access
            self.socket._sock.close()  # pylint: disable=protected-access

            self.closed = True
