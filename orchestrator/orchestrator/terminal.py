# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import fcntl
import os
import pty
import struct
import termios
from typing import Any, Dict, Optional

from docker.client import DockerClient

from . import settings
from .docker import containers


class TerminalContainer:  # pylint: disable=too-many-instance-attributes
    def __init__(self, client: DockerClient, site_id: int, site_data: Dict[str, Any]) -> None:
        self.client = client
        self.site_id = site_id
        self.site_data = site_data

        self.container_name = "site_{:04d}_terminal".format(site_id)

        run_params = containers.gen_director_container_params(client, site_id, site_data)

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
            client, self.container_name, run_params=run_params
        )

        self.process: Optional[asyncio.subprocess.Process] = None  # pylint: disable=no-member

        self.fd: Optional[int] = None

    async def start_process(self) -> None:
        env = {}
        if self.site_data.get("database_url"):
            env["DATABASE_URL"] = self.site_data["database_url"]

        args = [
            "docker",
            "exec",
            "--interactive",
            "--tty",
            "--workdir=/site",
        ]

        # We pass the actual value in the subprocess environment
        args.extend("--env={}".format(key) for key in env)

        args.extend([self.container.id, "sh"])

        process_env = dict(os.environ)
        process_env.update(env)

        self.fd, self.fd_slave = pty.openpty()

        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdin=self.fd_slave,
            stdout=self.fd_slave,
            stderr=self.fd_slave,
            env=process_env,
        )

        self.resize(24, 80)

        self.heartbeat()

    def heartbeat(self) -> None:
        with self.container.attach_socket(params={"stdin": 1, "stream": 1}, ws=False) as sock:
            # We have to pry into the internals of docker-py a little. There is no known way around
            # this.
            # Sources:
            # https://stackoverflow.com/q/26843625
            # https://github.com/docker/docker-py/pull/239#issuecomment-246149032

            sock._sock.send(b"\n")  # pylint: disable=protected-access

    async def read(self, bufsize: int) -> bytes:
        assert self.fd is not None

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(None, os.read, self.fd, bufsize)

    def write(self, data: bytes) -> None:
        assert self.fd is not None

        os.write(self.fd, data)

    def resize(self, rows: int, cols: int) -> None:
        assert self.fd is not None

        buf = struct.pack("HHHH", rows, cols, 0, 0)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, buf)  # type: ignore
        fcntl.ioctl(self.fd_slave, termios.TIOCSWINSZ, buf)  # type: ignore

    async def wait(self) -> int:
        assert self.process is not None

        if self.process.returncode is not None:
            return self.process.returncode
        else:
            return await self.process.wait()

    def terminate(self) -> None:
        assert self.process is not None

        self.process.terminate()

    def kill(self) -> None:
        assert self.process is not None

        self.process.kill()
