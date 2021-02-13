# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import subprocess
import time
from typing import AsyncGenerator, Optional, Union

from docker.client import DockerClient

from .docker.services import get_director_service_name, get_service_by_name


class DirectorSiteLogFollower:
    def __init__(self, client: DockerClient, site_id: int) -> None:
        self.client = client
        self.site_id = site_id

        self.service = get_service_by_name(client, get_director_service_name(self.site_id))

        self.stopped = True

        self.proc: Optional[asyncio.subprocess.Process] = None  # pylint: disable=no-member
        self.proc_start_time = 0.0

        # The process will be restarted this often
        self.proc_life_timeout = 90.0

    async def start(
        self, *, since_time: Union[int, float, None] = None, last_n: Optional[int] = None
    ) -> None:
        if self.service is None:
            self.stopped = True
            return

        args = ["docker", "service", "logs", "--follow", "--raw"]

        if since_time is not None:
            args.extend(("--since", str(since_time)))
        else:
            args.extend(("--tail", str(last_n if last_n is not None else 0)))

        args.append(self.service.id)

        self.proc = await asyncio.create_subprocess_exec(
            *args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
        )

        self.proc_start_time = time.time()

        self.stopped = False

    async def iter_lines(self) -> AsyncGenerator[str, None]:
        if self.stopped:
            return

        assert self.proc is not None
        assert self.proc.stdout is not None

        while True:
            timeout = max(self.proc_life_timeout - (time.time() - self.proc_start_time), 0)

            try:
                yield await self._read_line(timeout=timeout)
            except asyncio.TimeoutError:
                since_time = time.time()
                # Kill the process
                await self.stop(timeout=2)

                # Now read the lines and yield them out
                try:
                    while True:
                        line = await self._read_line(timeout=0.5)
                        if not line:
                            break

                        yield line
                except asyncio.TimeoutError:
                    pass

                # And start the process again
                await self.start(since_time=since_time)

    async def _read_line(self, *, timeout: Union[int, float, None]) -> str:
        if self.stopped:
            return ""

        assert self.proc is not None
        assert self.proc.stdout is not None

        return (await asyncio.wait_for(self.proc.stdout.readline(), timeout=timeout)).decode()

    async def stop(self, *, timeout: Union[int, float] = 5) -> None:
        if self.stopped:
            return

        assert self.proc is not None

        try:
            self.proc.terminate()
        except ProcessLookupError:
            pass

        self.stopped = True

        try:
            await asyncio.wait_for(self.proc.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.proc.kill()
            await self.proc.wait()

    async def __aenter__(self) -> "DirectorSiteLogFollower":
        return self

    async def __aexit__(  # type: ignore  # pylint: disable=invalid-name
        self, exc_type, exc, tb
    ) -> None:
        await self.stop()
