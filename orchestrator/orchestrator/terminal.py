# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import os
import socket
from typing import Any, Dict, Optional

from docker.client import DockerClient
from docker.models.containers import Container

from . import settings
from .docker import containers
from .utils import run_in_executor


class TerminalContainer:  # pylint: disable=too-many-instance-attributes
    def __init__(self, client: DockerClient, site_id: int, site_data: Dict[str, Any]) -> None:
        self.client = client
        self.site_id = site_id
        self.site_data = site_data

        self.container_name = "site_{:04d}_terminal".format(site_id)

        self.container: Optional[Container] = None

        self.exec_id: Optional[str] = None

        self.socket: Optional[socket.SocketIO] = None

    async def start(self) -> None:
        await self._start_attach()

        # The default timeout is 60 seconds, which is way too low
        assert self.socket is not None
        self.socket._sock.settimeout(None)  # pylint: disable=protected-access

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
                "auto_remove": True,
                "stdin_open": True,
            }
        )

        self.container = containers.get_or_create_container(
            self.client, self.container_name, run_params=run_params,
        )

        assert self.container is not None

        env = {}
        if self.site_data.get("database_url"):
            env["DATABASE_URL"] = self.site_data["database_url"]

        args = ["sh"]

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

    @run_in_executor(None)
    def read(self, bufsize: int) -> bytes:
        assert self.socket is not None

        return self.socket.read(bufsize)

    @run_in_executor(None)
    def write(self, data: bytes) -> None:
        assert self.socket is not None

        # self.socket.write() doesn't work -- the SocketIO object is not marked as writable.
        os.write(self.socket.fileno(), data)

    @run_in_executor(None)
    def resize(self, rows: int, cols: int) -> None:
        assert self.exec_id is not None

        self.client.api.exec_resize(self.exec_id, height=rows, width=cols)

    @run_in_executor(None)
    def close(self) -> None:
        assert self.socket is not None

        self.socket.close()
