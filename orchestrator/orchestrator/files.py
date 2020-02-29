# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
import os
import selectors
import subprocess
from typing import (  # pylint: disable=unused-import
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    Generator,
    Iterable,
    List,
    Optional,
    TypeVar,
    Union,
    cast,
)

from . import settings

HELPER_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "helpers/files-helper.py",
)

HELPER_SPECIAL_EXIT_CODE = 145  # Denotes that the text shown on stderr is safe to show to the user

BUFSIZE = 4096

T = TypeVar("T")


class SiteFilesException(Exception):
    pass


def get_site_directory_path(site_id: int) -> str:
    id_parts = ("{:02d}".format(site_id // 100), "{:02d}".format(site_id % 100))

    return os.path.join(settings.SITES_DIRECTORY, *id_parts)


def check_run_sh_exists(site_id: int) -> bool:
    site_directory = get_site_directory_path(site_id)

    return any(
        os.path.exists(os.path.join(site_directory, suffix))
        for suffix in ["run.sh", "private/run.sh", "public/run.sh"]
    )


def _run_helper_script_prog(
    callback: Callable[[List[str], Dict[str, Any]], T], args: List[str], kwargs: Dict[str, Any]
) -> T:
    # SITE_DIRECTORY_COMMAND_PREFIX may be a sudo command, so we can't be sure the user the
    # script will be running at will actually have access to the script.
    # So we open the helper script, pass the file descriptor to the child process, and tell
    # Python to read the program from /dev/fd/<fd>.

    with open(HELPER_SCRIPT_PATH) as f_obj:
        text = f_obj.read()

    real_args = [
        *settings.SITE_DIRECTORY_COMMAND_PREFIX,
        "unshare",
        "--map-root-user",
        "--",
        "python3",
        "-c",
        'import os; exec(os.environ["ORCHESTRATOR_HELPER_PROG"])',
        *args,
    ]

    kwargs.setdefault("env", os.environ)
    kwargs["env"]["ORCHESTRATOR_HELPER_PROG"] = text

    return callback(real_args, kwargs)


def run_helper_script_prog(args: List[str], **kwargs: Any) -> "subprocess.Popen[bytes]":
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


def ensure_site_directories_exist(site_id: int) -> None:
    site_dir = get_site_directory_path(site_id)

    subprocess.run(
        [*settings.SITE_DIRECTORY_COMMAND_PREFIX, "mkdir", "-p", "--", site_dir],
        stdin=subprocess.DEVNULL,
        check=True,
    )

    proc = run_helper_script_prog(
        ["setup", site_dir],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
        raise SiteFilesException(stderr.decode().strip())
    elif proc.returncode != 0:
        raise SiteFilesException("Internal error")


def list_site_files(site_id: int, relpath: str) -> List[Dict[str, str]]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["ls", site_dir, relpath],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = proc.communicate()

    if proc.returncode == 0:
        return cast(List[Dict[str, str]], json.loads(stdout.decode().strip()))
    elif proc.returncode == HELPER_SPECIAL_EXIT_CODE:
        raise SiteFilesException(stderr.decode().strip())
    else:
        raise SiteFilesException("Internal error")


def stream_site_file(site_id: int, relpath: str) -> Generator[bytes, None, None]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["get", site_dir, relpath, str(settings.MAX_FILE_DOWNLOAD_BYTES)],
        bufsize=0,  # THIS IS IMPORTANT
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    line = proc.stderr.readline().decode().strip()
    if line != "OK":
        raise SiteFilesException(line)

    errors = ""

    selector = selectors.DefaultSelector()
    selector.register(proc.stdout, selectors.EVENT_READ)
    selector.register(proc.stderr, selectors.EVENT_READ)

    while proc.poll() is None:
        ready_files = selector.select(timeout=300)

        for key, _ in ready_files:
            if key.fileobj == proc.stdout:
                buf = proc.stdout.read(BUFSIZE)
                if not buf:
                    break

                yield buf
            elif key.fileobj == proc.stderr:
                errors += proc.stderr.read(BUFSIZE).decode()

    while True:
        buf = proc.stdout.read(BUFSIZE)
        if not buf:
            break

        yield buf

    errors += proc.stderr.read().decode()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(errors.strip())
        else:
            raise SiteFilesException("Internal error")


def write_site_file(
    site_id: int,
    relpath: str,
    data: Union[bytes, Iterable[bytes]],
    *,
    mode_str: Optional[str] = None,
) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["write", site_dir, relpath]
    if mode_str is not None:
        args.append(mode_str)

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    if isinstance(data, bytes):
        proc.stdin.write(data)
    else:
        for chunk in data:
            proc.stdin.write(chunk)

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
        else:
            raise SiteFilesException("Internal error")


def remove_all_site_files_dangerous(site_id: int) -> None:
    site_dir = get_site_directory_path(site_id)
    proc = run_helper_script_prog(
        ["remove-all-site-files-dangerous", site_dir],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
        else:
            raise SiteFilesException("Internal error")


def remove_site_file(site_id: int, relpath: str) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["rm", site_dir, relpath]

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
        else:
            raise SiteFilesException("Internal error")


def remove_site_directory_recur(site_id: int, relpath: str) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["rmdir-recur", site_dir, relpath]

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
        else:
            raise SiteFilesException("Internal error")


def make_site_directory(site_id: int, relpath: str, *, mode_str: Optional[str] = None) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["mkdir", site_dir, relpath]
    if mode_str is not None:
        args.append(mode_str)

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
        else:
            raise SiteFilesException("Internal error")


def rename_path(site_id: int, oldpath: str, newpath: str) -> None:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["rename", site_dir, oldpath, newpath],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
        else:
            raise SiteFilesException("Internal error")


def chmod_path(site_id: int, relpath: str, *, mode_str: str) -> None:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["chmod", site_dir, relpath, mode_str],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    if proc.returncode != 0:
        if proc.returncode == HELPER_SPECIAL_EXIT_CODE:
            raise SiteFilesException(stderr.decode().strip())
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

        self.proc.stdin.write(b"+" + relpath.encode() + b"\n")
        await self.proc.stdin.drain()

    async def rm_watch(self, relpath: str) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        assert self.proc.stdin is not None

        self.proc.stdin.write(b"-" + relpath.encode() + b"\n")
        await self.proc.stdin.drain()

    async def aiter_events(self) -> AsyncGenerator[Dict[str, Any], None]:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        assert self.proc.stdout is not None

        while True:
            try:
                line = await self.proc.stdout.readline()
            except OSError:
                line = b""

            if not line:
                break

            yield json.loads(line)
