# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
import os
import subprocess
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, TypeVar, Union

from . import settings

HELPER_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "helpers/files-helper.py",
)

HELPER_SPECIAL_EXIT_CODE = 145  # Denotes that the text shown on stderr is safe to show to the user

T = TypeVar("T")


class SiteFilesException(Exception):
    pass


def get_site_directory_path(site_id: int) -> str:
    id_parts = ("{:02d}".format(site_id // 100), "{:02d}".format(site_id % 100))

    return os.path.join(settings.SITES_DIRECTORY, *id_parts)


def ensure_site_directories_exist(site_id: int) -> None:
    site_dir = get_site_directory_path(site_id)

    directories = [
        site_dir,
        os.path.join(site_dir, "private"),
        os.path.join(site_dir, "public"),
    ]

    subprocess.run(
        [
            *settings.SITE_DIRECTORY_COMMAND_PREFIX,
            "/bin/sh",
            "-c",
            'set -e; for fname in "$@"; do mkdir -p -- "$fname"; chmod 0755 -- "$fname"; done',
            "/bin/sh",
            *directories,
        ],
        stdin=subprocess.DEVNULL,
        check=True,
    )


def _run_helper_script_prog(
    callback: Callable[[List[str], Dict[str, Any]], T], args: List[str], kwargs: Dict[str, Any]
) -> T:
    # SITE_DIRECTORY_COMMAND_PREFIX may be a sudo command, so we can't be sure the user the
    # script will be running at will actually have access to the script.
    # So we open the helper script, pass the file descriptor to the child process, and tell
    # Python to read the program from /dev/fd/<fd>.

    with open(HELPER_SCRIPT_PATH) as f_obj:
        os.set_inheritable(f_obj.fileno(), True)

        real_args = [
            *settings.SITE_DIRECTORY_COMMAND_PREFIX,
            "unshare",
            "--map-root-user",
            "--",
            "python3",
            "/dev/fd/{}".format(f_obj.fileno()),
            *args,
        ]

        kwargs["pass_fds"] = list(kwargs.get("pass_fds", []))
        kwargs["pass_fds"].append(f_obj.fileno())

        return callback(real_args, kwargs)


def run_helper_script_prog(args: List[str], **kwargs: Any) -> subprocess.Popen:
    return _run_helper_script_prog(
        lambda real_args, kwargs: subprocess.Popen(real_args, **kwargs), args, kwargs,
    )


async def run_helper_script_prog_async(
    args: List[str], **kwargs: Any
) -> asyncio.subprocess.Process:  # pylint: disable=no-member
    return await _run_helper_script_prog(
        lambda real_args, kwargs: asyncio.subprocess.create_subprocess_exec(  # pylint: disable=no-member,line-too-long # noqa
            *real_args, **kwargs,
        ),
        args,
        kwargs,
    )


def list_site_files(site_id: int, relpath: str) -> List[Dict[str, str]]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["ls", site_dir, relpath],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    stdout, stderr = proc.communicate()

    if proc.returncode == 0:
        return json.loads(stdout.strip())
    elif proc.returncode == HELPER_SPECIAL_EXIT_CODE:
        raise SiteFilesException(stderr.strip())
    else:
        raise SiteFilesException("Internal error")


def get_site_file(site_id: int, relpath: str) -> List[str]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["get", site_dir, relpath, str(settings.MAX_FILE_DOWNLOAD_BYTES)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    stdout, stderr = proc.communicate()

    if proc.returncode == 0:
        return stdout
    elif proc.returncode == HELPER_SPECIAL_EXIT_CODE:
        raise SiteFilesException(stderr.strip())
    else:
        raise SiteFilesException("Internal error")


class SiteFilesMonitor:
    def __init__(self, site_id: int) -> None:
        self.site_id = site_id

        self.proc: Optional[asyncio.subprocess.Process] = None  # pylint: disable=no-member

    async def start(self) -> None:
        if self.proc is not None:
            raise Exception("SiteFilesMonitor.start() called multiple times")

        self.proc = await run_helper_script_prog_async(
            ["monitor", get_site_directory_path(self.site_id)],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    async def wait(self) -> int:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        return await self.proc.wait()

    def terminate(self) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        self.proc.terminate()

    def kill(self) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        self.proc.kill()

    async def stop_wait(self, *, timeout: Union[int, float]) -> None:
        self.terminate()

        try:
            await asyncio.wait_for(self.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            self.kill()
            await self.wait()

    async def add_watch(self, relpath: str) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        assert self.proc.stdin is not None

        await self.proc.stdin.write(b"+" + relpath.encode())  # type: ignore

    async def rm_watch(self, relpath: str) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        assert self.proc.stdin is not None

        await self.proc.stdin.write(b"-" + relpath.encode())  # type: ignore

    async def aiter_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        assert self.proc.stdout is not None

        while True:
            line = await self.proc.stdout.readline()

            if not line:
                break

            yield json.loads(line)
