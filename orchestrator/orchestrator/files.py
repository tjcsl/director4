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
    Tuple,
    TypeVar,
    Union,
    cast,
)

from . import settings

HELPER_SCRIPT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "helpers/files-helper.py",
)

HELPER_SCRIPT_VENDOR_PATH = os.path.join(
    os.path.dirname(os.path.dirname(__file__)), "helpers/vendor",
)

HELPER_SPECIAL_EXIT_CODE = 145  # Denotes that the text shown on stderr is safe to show to the user

BUFSIZE = 4096

T = TypeVar("T")


class SiteFilesException(Exception):
    pass


class SiteFilesUserViewableException(SiteFilesException):
    pass


def raise_for_process_result(returncode: int, stderr: Union[str, bytes]) -> None:
    if returncode == 0:
        return

    if isinstance(stderr, bytes):
        try:
            stderr = stderr.decode()
        except UnicodeDecodeError:
            stderr = cast(bytes, stderr).decode("latin1")

    if returncode == HELPER_SPECIAL_EXIT_CODE:
        raise SiteFilesUserViewableException(stderr.strip())
    else:
        raise SiteFilesException(stderr.strip())


def get_site_directory_path(site_id: int) -> str:
    id_parts = ("{:02d}".format(site_id // 100), "{:02d}".format(site_id % 100))

    return os.path.join(settings.SITES_DIRECTORY, *id_parts)


def check_run_sh_exists(site_id: int) -> bool:
    site_directory = get_site_directory_path(site_id)

    return any(
        os.path.exists(os.path.join(site_directory, suffix))
        for suffix in ["run.sh", "private/run.sh", "public/run.sh"]
    )


def _load_vendor_modules(path: str) -> Iterable[Tuple[str, str]]:
    # This is very closely tied to the custom import hooks in helpers/files-helper.py
    # Don't touch anything here unless you have read both this code and that code carefully
    # and understand how this whole systemworks.

    for fname in os.listdir(path):
        if fname[0] == ".":
            continue

        fpath = os.path.join(path, fname)

        if os.path.isfile(fpath) and fname.endswith(".py") and "." not in fname[:-3]:
            with open(fpath) as f_obj:
                yield (fname[:-3], f_obj.read())
        elif os.path.isdir(fpath) and "." not in fname:
            for name, text in _load_vendor_modules(fpath):
                yield (fname + "." + name, text)


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

    for name, text in _load_vendor_modules(HELPER_SCRIPT_VENDOR_PATH):
        kwargs["env"]["ORCHESTRATOR_HELPER_VENDOR_" + name] = text

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
        ["ensure-directories-exist", site_dir],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def list_site_files(site_id: int, relpath: str) -> List[Dict[str, str]]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["ls", site_dir, relpath],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    stdout, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)

    return cast(List[Dict[str, str]], json.loads(stdout.decode().strip()))


def stream_site_file(site_id: int, relpath: str) -> Generator[bytes, None, None]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["get", site_dir, relpath, str(settings.MAX_FILE_DOWNLOAD_BYTES)],
        bufsize=0,  # THIS IS IMPORTANT
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert proc.stderr is not None
    assert proc.stdout is not None

    line = proc.stderr.readline().strip()
    if line != b"OK":
        try:
            proc.terminate()
        except ProcessLookupError:
            pass

        try:
            proc.wait(timeout=0.5)
        except subprocess.TimeoutExpired:
            try:
                proc.kill()
            except ProcessLookupError:
                pass

        proc.wait()

        raise_for_process_result(proc.returncode, line + b"\n" + proc.stderr.read())

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

    raise_for_process_result(proc.returncode, errors)


def download_zip_site_dir(site_id: int, relpath: str) -> Generator[bytes, None, None]:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        [
            "download-zip",
            site_dir,
            relpath,
            str(settings.MAX_FILE_DOWNLOAD_BYTES),
            str(settings.MAX_ZIP_FILES),
        ],
        bufsize=0,  # THIS IS IMPORTANT
        stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    assert proc.stderr is not None
    assert proc.stdout is not None

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

    raise_for_process_result(proc.returncode, errors)


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

    assert proc.stdin is not None

    if isinstance(data, bytes):
        proc.stdin.write(data)
    else:
        for chunk in data:
            proc.stdin.write(chunk)

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def create_site_file(site_id: int, relpath: str, *, mode_str: Optional[str] = None) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["create", site_dir, relpath]
    if mode_str is not None:
        args.append(mode_str)

    proc = run_helper_script_prog(
        args, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def remove_all_site_files_dangerous(site_id: int) -> None:
    site_dir = get_site_directory_path(site_id)
    proc = run_helper_script_prog(
        ["remove-all-site-files-dangerous", site_dir],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def remove_site_file(site_id: int, relpath: str) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["rm", site_dir, relpath]

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def remove_site_directory_recur(site_id: int, relpath: str) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["rmdir-recur", site_dir, relpath]

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def make_site_directory(site_id: int, relpath: str, *, mode_str: Optional[str] = None) -> None:
    site_dir = get_site_directory_path(site_id)

    args = ["mkdir", site_dir, relpath]
    if mode_str is not None:
        args.append(mode_str)

    proc = run_helper_script_prog(
        args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def rename_path(site_id: int, oldpath: str, newpath: str) -> None:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["rename", site_dir, oldpath, newpath],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


def chmod_path(site_id: int, relpath: str, *, mode_str: str) -> None:
    site_dir = get_site_directory_path(site_id)

    proc = run_helper_script_prog(
        ["chmod", site_dir, relpath, mode_str],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    _, stderr = proc.communicate()

    raise_for_process_result(proc.returncode, stderr)


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

    def kill(self) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        try:
            self.proc.kill()
        except ProcessLookupError:
            pass

    async def stop_wait(self, *, timeout: Union[int, float]) -> None:
        if self.proc is None:
            raise Exception("SiteFilesMonitor.start() was not called")

        assert self.proc.stdin is not None

        self.proc.stdin.write(b"q\n")
        await self.proc.stdin.drain()

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
