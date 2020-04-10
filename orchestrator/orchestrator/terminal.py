# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import socket
from typing import Any, Dict, Optional

from docker.client import DockerClient
from docker.errors import ImageNotFound, NotFound
from docker.models.containers import Container

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

    async def start(self) -> None:
        await self._start_attach()

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

    @run_in_executor(None)
    def _start_attach(self) -> None:
        """Internal function that runs in an executor and performs all the long-running synchronous
        operations needed to create the container (if necessary) and attach to it."""
        run_params = containers.gen_director_container_params(
            self.client, self.site_id, self.site_data
        )

        run_params.update(
            {
                "command": [
                    "sh",
                    "-c",
                    'while timeout "$1" head -n 1 &>/dev/null; do true; done',
                    "sh",
                    str(settings.SITE_TERMINAL_KEEPALIVE_TIMEOUT),
                ],
                "read_only": True,
                "auto_remove": True,
                "stdin_open": True,
            }
        )

        self.container = containers.get_or_create_container(
            self.client, self.container_name, run_params=run_params,
        )

        assert self.container is not None

        try:
            image = self.client.images.get(run_params["image"])
        except ImageNotFound:
            pass
        else:
            if self.container.image.id != image.id:
                self.container.stop()
                try:
                    self.container.wait()
                except NotFound:
                    pass

                self.container = containers.get_or_create_container(
                    self.client, self.container_name, run_params=run_params,
                )

        env = gen_director_container_env(self.client, self.site_id, self.site_data)

        # See docs/UMASK.md before touching this
        args = [
            "sh",
            "-c",
            'umask "$1"; if [ -x /bin/bash ]; then exec bash; fi; exec sh',
            "sh",
            oct(settings.SITE_UMASK)[2:],
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
