# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import array
import asyncio
import fcntl
import os
import pty
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

        self.stdin_fd: Optional[int] = None
        self.stdout_fd: Optional[int] = None

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

        self.stdin_fd, stdin_fd_slave = pty.openpty()
        self.stdout_fd, stdout_fd_slave = pty.openpty()

        self.process = await asyncio.create_subprocess_exec(
            *args,
            stdin=stdin_fd_slave,
            stdout=stdout_fd_slave,
            stderr=stdout_fd_slave,
            start_new_session=True,
            env=process_env,
        )

        self.resize(80, 24)

    def heartbeat(self) -> None:
        with self.client.attach_socket(params={"stdin": 1, "stream": 1}, ws=False) as sock:
            # We have to pry into the internals of docker-py a little. There is no known way around
            # this.
            # Sources:
            # https://stackoverflow.com/q/26843625
            # https://github.com/docker/docker-py/pull/239#issuecomment-246149032

            sock._sock.send(b"\n")  # pylint: disable=protected-access

    async def read(self, bufsize: int) -> bytes:
        assert self.stdout_fd is not None

        loop = asyncio.get_event_loop()

        return await loop.run_in_executor(None, os.read, self.stdout_fd, bufsize)

    def write(self, data: bytes) -> None:
        assert self.stdin_fd is not None

        os.write(self.stdin_fd, data)

    def resize(self, width: int, height: int) -> None:
        assert self.stdout_fd is not None

        buf = array.array("h", [width, height, 0, 0])
        fcntl.ioctl(self.stdout_fd, termios.TIOCSWINSZ, buf)  # type: ignore
        fcntl.ioctl(self.stdin_fd, termios.TIOCSWINSZ, buf)  # type: ignore

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
