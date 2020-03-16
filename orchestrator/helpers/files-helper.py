# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import importlib
import importlib.util
import json
import os
import resource
import select
import shutil
import stat
import string
import sys
from typing import Any, Dict, List, Optional


SPECIAL_EXIT_CODE = 145  # Denotes that the text shown on stderr is safe to show to the user

BUFSIZE = 4096


def chroot_into(directory: str) -> None:
    if os.getuid() != 0:
        print("Please run this in a user namespace", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    os.chroot(directory)
    os.chdir("/")


# Later, this function may support more complicated strings
def get_new_mode(old_mode: int, mode_str: str) -> int:
    if set(mode_str) < set("01234567"):
        return int(mode_str, base=8)
    elif mode_str.startswith(("+", "-")) and set(mode_str[1:]) < set("rwx"):
        mode_masks = {
            "r": stat.S_IRUSR + stat.S_IRGRP + stat.S_IROTH,
            "w": stat.S_IWUSR + stat.S_IWGRP + stat.S_IWOTH,
            "x": stat.S_IXUSR + stat.S_IXGRP + stat.S_IXOTH,
        }
        mask = 0
        for ch in mode_str[1:]:
            if ch in mode_masks:
                mask |= mode_masks[ch]

        return (old_mode | mask) if mode_str[0] == "+" else (old_mode & (0o777 ^ mask))
    else:
        print("Invalid mode string", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def update_mode(path: str, mode_str: str) -> None:
    old_mode = os.stat(path).st_mode
    new_mode = get_new_mode(old_mode, mode_str)
    os.chmod(path, new_mode)


def construct_scandir_file_dicts(dirpath: str) -> List[Dict[str, Optional[str]]]:
    items = []
    for entry in os.scandir(dirpath or "."):
        fname = os.path.join(dirpath, entry.name)
        item = {
            "fname": fname,
            "filetype": "unknown",
            "dest": None,
            "mode": None,
        }

        try:
            item["mode"] = entry.stat(follow_symlinks=False).st_mode
        except OSError:
            pass

        try:
            if entry.is_symlink():
                item["filetype"] = "link"
                try:
                    item["dest"] = os.readlink(fname)
                except OSError:
                    pass
            elif entry.is_dir():
                item["filetype"] = "dir"
            elif entry.is_file():
                item["filetype"] = "file"
            else:
                item["filetype"] = "other"
        except OSError:
            pass

        items.append(item)

    return items


def construct_file_event_dict(fname: str) -> Dict[str, Optional[str]]:
    event_info = {
        "fname": fname,
        "filetype": "unknown",
        "dest": None,
        "mode": None,
    }

    try:
        file_stat = os.lstat(fname)
    except OSError:
        pass
    else:
        event_info["mode"] = file_stat.st_mode

        if stat.S_ISLNK(file_stat.st_mode):
            event_info["filetype"] = "link"
            try:
                event_info["dest"] = os.readlink(fname)
            except OSError:
                pass
        elif stat.S_ISDIR(file_stat.st_mode):
            event_info["filetype"] = "dir"
        elif stat.S_ISREG(file_stat.st_mode):
            event_info["filetype"] = "file"
        else:
            event_info["filetype"] = "other"

    return event_info


def setup_cmd(site_directory: str) -> None:
    chroot_into(site_directory)

    directories = [
        "/private",
        "/public",
    ]

    for directory in directories:
        os.makedirs(directory, exist_ok=True)


def ls_cmd(site_directory: str, relpath: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    print(json.dumps(construct_scandir_file_dicts(relpath)))


def chmod_cmd(site_directory: str, relpath: str, mode_str: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    update_mode(relpath, mode_str)


def rename_cmd(site_directory: str, oldpath: str, newpath: str) -> None:
    if oldpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    if newpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    if os.path.exists(newpath) or os.path.islink(newpath):
        print("File already exists", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    try:
        os.rename(oldpath, newpath)
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def mkdir_cmd(site_directory: str, relpath: str, mode_str: Optional[str] = None) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    os.makedirs(relpath, mode=0o755, exist_ok=True)
    if mode_str is not None and mode_str != "":
        update_mode(relpath, mode_str)


def rm_cmd(site_directory: str, relpath: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    if os.path.exists(relpath) or os.path.islink(relpath):
        os.remove(relpath)


def rmdir_recur_cmd(site_directory: str, relpath: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    if os.path.isdir(relpath):
        shutil.rmtree(relpath)


def get_cmd(site_directory: str, relpath: str, max_size_str: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    try:
        max_size = int(max_size_str)
    except ValueError:
        print("Invalid max size", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    try:
        if os.path.getsize(relpath) > max_size:
            print("File too large", file=sys.stderr)
            sys.exit(SPECIAL_EXIT_CODE)

        with open(relpath, "rb") as f_obj:
            f_obj.seek(0, os.SEEK_END)
            if f_obj.tell() > max_size:
                print("File too large", file=sys.stderr)
                sys.exit(SPECIAL_EXIT_CODE)
            f_obj.seek(0, os.SEEK_SET)

            print("OK", file=sys.stderr, flush=True)

            for chunk in iter(lambda: f_obj.read(BUFSIZE), b""):
                sys.stdout.buffer.write(chunk)
                sys.stdout.flush()
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def write_cmd(site_directory: str, relpath: str, mode_str: Optional[str] = None) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    try:
        mode_updated = False
        if mode_str is not None and os.path.exists(relpath):
            update_mode(relpath, mode_str)
            mode_updated = True

        with open(relpath, "wb") as f_obj:
            while True:
                chunk = sys.stdin.buffer.read1(BUFSIZE)
                if not chunk:
                    break

                f_obj.write(chunk)
                f_obj.flush()

        if mode_str is not None and not mode_updated:
            update_mode(relpath, mode_str)
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def monitor_cmd(site_directory: str) -> None:
    chroot_into(site_directory)

    inotify = inotify_simple.INotify()
    directory_watch_flags = (
        # File created in directory
        inotify_simple.flags.CREATE
        # File deleted in directory
        | inotify_simple.flags.DELETE
        # File moved from directory
        | inotify_simple.flags.MOVED_FROM
        # File moved into directory
        | inotify_simple.flags.MOVED_TO
        # Directory moved
        | inotify_simple.flags.MOVE_SELF
        # Directory deleted
        | inotify_simple.flags.DELETE_SELF
        # Attributes changed
        | inotify_simple.flags.ATTRIB
        # Don't follow symlinks
        | inotify_simple.flags.DONT_FOLLOW
        # Raise an error if it's not a directory
        | inotify_simple.flags.ONLYDIR
    )

    stdin_data = b""

    wds_by_fname: Dict[str, int] = {}
    fnames_by_wd: Dict[int, str] = {}

    def remove_watch_and_subwatches(fname: str) -> None:
        for wd, wd_fname in list(fnames_by_wd.items()):
            # Remove for the directory itself, as well as all subdirectories
            if os.path.commonpath([fname, wd_fname]) == fname:
                try:
                    inotify.rm_watch(wd)
                except OSError:
                    pass

                fnames_by_wd.pop(wd, None)
                wds_by_fname.pop(wd_fname, None)

    while True:
        read_fds = select.select([inotify.fileno(), 0], [], [], 30)[0]

        for fd in read_fds:
            if fd == 0:
                # Input formats:
                # +<fname> -- begin watching the directory at fname
                # -<fname> -- stop watching the directory at fname
                # q -- quit
                # Input format errors cause the program to exit with an error.
                # Other errors (directories not existing, etc.) are silently
                # ignored as they may have been caused by race conditions.

                stdin_data += sys.stdin.buffer.read1(BUFSIZE)  # type: ignore
                while b"\n" in stdin_data:
                    index = stdin_data.find(b"\n")
                    line = stdin_data[:index]  # Implicitly removing the trailing newline
                    stdin_data = stdin_data[index + 1:]

                    if not line:
                        # Ignore empty lines
                        continue

                    operation = bytes((line[0],))
                    try:
                        fname = line[1:].decode().strip("\r\n")
                    except UnicodeDecodeError:
                        print("Invalid input", file=sys.stderr)
                        sys.exit(SPECIAL_EXIT_CODE)

                    if operation == b"+":
                        # Add watch
                        try:
                            watch_desc = inotify.add_watch(fname or ".", directory_watch_flags)
                        except OSError as ex:
                            print(json.dumps({"event": "error", "fname": fname, "error": str(ex)}), flush=True)
                        else:
                            wds_by_fname[fname] = watch_desc
                            fnames_by_wd[watch_desc] = fname

                            # Send the initial listing
                            # Sent as "create" events because there are only "create"
                            # and "delete" events
                            for event_info in construct_scandir_file_dicts(fname):
                                event_info["event"] = "create"

                                # flush=True is very important
                                print(json.dumps(event_info), flush=True)
                    elif operation == b"-":
                        # Remove watch
                        remove_watch_and_subwatches(fname)
                    elif operation == b"q":
                        # Quit
                        sys.exit(0)
                    else:
                        print("Invalid input", file=sys.stderr)
                        sys.exit(SPECIAL_EXIT_CODE)
            elif fd == inotify.fileno():
                for event in inotify.read():
                    if event.wd not in fnames_by_wd:
                        continue

                    fname = os.path.join(fnames_by_wd[event.wd], event.name)

                    if (
                        event.mask & inotify_simple.flags.MOVE_SELF  # Directory moved
                        or event.mask & inotify_simple.flags.DELETE_SELF  # Directory deleted
                    ):
                        # Remove this watch and all subwatches
                        # We need to do this because now that this directory is being moved we
                        # don't know where it's going to go, so we can't continue to watch it.
                        remove_watch_and_subwatches(fnames_by_wd[event.wd])

                        event_info = {
                            "fname": fname,
                            "event": "delete",
                        }
                    elif (
                        event.mask & inotify_simple.flags.MOVED_FROM  # Subfile moved somewhere else
                        or event.mask & inotify_simple.flags.DELETE  # Subfile deleted
                    ):
                        event_info = {
                            "fname": fname,
                            "event": "delete",
                        }
                    elif (
                        event.mask & inotify_simple.flags.CREATE  # Subfile created
                        or event.mask & inotify_simple.flags.MOVED_TO,  # Subfile moved here
                    ):
                        event_info = construct_file_event_dict(fname)
                        event_info["event"] = "create"
                    elif event.mask & inotify_simple.flags.ATTRIB:  # Attributes changed
                        event_info = construct_file_event_dict(fname)
                        event_info["event"] = "update"
                    else:
                        # We only watch for specific events, but there are some
                        # that get triggered anyway.
                        continue

                    # flush=True is very important
                    print(json.dumps(event_info), flush=True)


def remove_all_site_files_dangerous_cmd(site_directory: str) -> None:
    try:
        shutil.rmtree(site_directory)
    except OSError as ex:
        print("Error: {}".format(ex), file=sys.stderr)


def main(argv: List[str]) -> None:
    if len(argv) < 2:
        print("Please specify a command", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    resource.setrlimit(resource.RLIMIT_AS, (200 * 1024 * 1024, 200 * 1024 * 1024))

    commands = {
        "setup": (setup_cmd, [1]),
        "ls": (ls_cmd, [2]),
        "get": (get_cmd, [3]),
        "write": (write_cmd, [2, 3]),
        "monitor": (monitor_cmd, [1]),
        "remove-all-site-files-dangerous": (remove_all_site_files_dangerous_cmd, [1]),
        "rm": (rm_cmd, [2]),
        "rmdir-recur": (rmdir_recur_cmd, [2]),
        "mkdir": (mkdir_cmd, [2, 3]),
        "chmod": (chmod_cmd, [3]),
        "rename": (rename_cmd, [3]),
    }

    if argv[1] in commands:
        cmd_func, cmd_argcounts = commands[argv[1]]

        if len(argv) - 2 not in cmd_argcounts:
            print("Invalid number of arguments to command {!r}".format(argv[1]), file=sys.stderr)
            sys.exit(SPECIAL_EXIT_CODE)

        cmd_func(*argv[2:])  # type: ignore
    else:
        print("Unknown command {!r}".format(argv[1]), file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


# Embedded copy of inotify_simple (license has been added in comments)
# Original source:
# https://github.com/chrisjbillington/inotify_simple/blob/f02a5ae7f69f6dd764da9ee527ce679d389f6033/inotify_simple.py  # noqa  # pylint: disable=line-too-long
_inotify_simple_source = r'''
# Copyright (c) 2016, Chris Billington
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided wi6h the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

from sys import version_info, getfilesystemencoding
from os import strerror, read
from enum import Enum, IntEnum
from collections import namedtuple
from struct import unpack_from, calcsize
from select import poll
from time import sleep
from ctypes import CDLL, get_errno, c_int
from errno import EINTR
from termios import FIONREAD
from fcntl import ioctl
from io import FileIO

PY2 = version_info.major < 3
if PY2:
    fsencode = lambda s: s if isinstance(s, str) else s.encode(getfilesystemencoding())
    # In 32-bit Python < 3 the inotify constants don't fit in an IntEnum:
    IntEnum = type('IntEnum', (long, Enum), {})
else:
    from os import fsencode, fsdecode


__version__ = '1.3.3'

__all__ = ['Event', 'INotify', 'flags', 'masks', 'parse_events']

_libc = None


def _libc_call(function, *args):
    """Wrapper which raises errors and retries on EINTR."""
    while True:
        rc = function(*args)
        if rc != -1:
            return rc
        errno = get_errno()
        if errno != EINTR:
            raise OSError(errno, strerror(errno))


#: A ``namedtuple`` (wd, mask, cookie, name) for an inotify event. On Python 3 the
#: :attr:`~inotify_simple.Event.name`  field is a ``str`` decoded with
#: ``os.fsdecode()``, on Python 2 it is ``bytes``.
Event = namedtuple('Event', ['wd', 'mask', 'cookie', 'name'])

_EVENT_FMT = 'iIII'
_EVENT_SIZE = calcsize(_EVENT_FMT)

CLOEXEC = 0o2000000
NONBLOCK = 0o0004000


class INotify(FileIO):

    #: The inotify file descriptor returned by ``inotify_init()``. You are
    #: free to use it directly with ``os.read`` if you'd prefer not to call
    #: :func:`~inotify_simple.INotify.read` for some reason. Also available as
    #: :func:`~inotify_simple.INotify.fileno`
    fd = property(FileIO.fileno)

    def __init__(self, inheritable=False, nonblocking=False):
        """File-like object wrapping ``inotify_init1()``. Raises ``OSError`` on failure.
        :func:`~inotify_simple.INotify.close` should be called when no longer needed.
        Can be used as a context manager to ensure it is closed, and can be used
        directly by functions expecting a file-like object, such as ``select``, or with
        functions expecting a file descriptor via
        :func:`~inotify_simple.INotify.fileno`.

        Args:
            inheritable (bool): whether the inotify file descriptor will be inherited by
                child processes. The default,``False``, corresponds to passing the
                ``IN_CLOEXEC`` flag to ``inotify_init1()``. Setting this flag when
                opening filedescriptors is the default behaviour of Python standard
                library functions since PEP 446.

            nonblocking (bool): whether to open the inotify file descriptor in
                nonblocking mode, corresponding to passing the ``IN_NONBLOCK`` flag to
                ``inotify_init1()``. This does not affect the normal behaviour of
                :func:`~inotify_simple.INotify.read`, which uses ``poll()`` to control
                blocking behaviour according to the given timeout, but will cause other
                reads of the file descriptor (for example if the application reads data
                manually with ``os.read(fd)``) to raise ``BlockingIOError`` if no data
                is available."""
        global _libc; _libc = _libc or CDLL('libc.so.6', use_errno=True)
        flags = (not inheritable) * CLOEXEC | bool(nonblocking) * NONBLOCK
        FileIO.__init__(self, _libc_call(_libc.inotify_init1, flags), mode='rb')
        self._poller = poll()
        self._poller.register(self.fileno())

    def add_watch(self, path, mask):
        """Wrapper around ``inotify_add_watch()``. Returns the watch
        descriptor or raises an ``OSError`` on failure.

        Args:
            path (str, bytes, or PathLike): The path to watch. Will be encoded with
                ``os.fsencode()`` before being passed to ``inotify_add_watch()``.

            mask (int): The mask of events to watch for. Can be constructed by
                bitwise-ORing :class:`~inotify_simple.flags` together.

        Returns:
            int: watch descriptor"""
        # Explicit conversion of Path to str required on Python < 3.6
        path = str(path) if hasattr(path, 'parts') else path
        return _libc_call(_libc.inotify_add_watch, self.fileno(), fsencode(path), mask)

    def rm_watch(self, wd):
        """Wrapper around ``inotify_rm_watch()``. Raises ``OSError`` on failure.

        Args:
            wd (int): The watch descriptor to remove"""
        _libc_call(_libc.inotify_rm_watch, self.fileno(), wd)

    def read(self, timeout=None, read_delay=None):
        """Read the inotify file descriptor and return the resulting
        :attr:`~inotify_simple.Event` namedtuples (wd, mask, cookie, name).

        Args:
            timeout (int): The time in milliseconds to wait for events if there are
                none. If negative or ``None``, block until there are events. If zero,
                return immediately if there are no events to be read.

            read_delay (int): If there are no events immediately available for reading,
                then this is the time in milliseconds to wait after the first event
                arrives before reading the file descriptor. This allows further events
                to accumulate before reading, which allows the kernel to coalesce like
                events and can decrease the number of events the application needs to
                process. However, this also increases the risk that the event queue will
                overflow due to not being emptied fast enough.

        Returns:
            generator: generator producing :attr:`~inotify_simple.Event` namedtuples

        .. warning::
            If the same inotify file descriptor is being read by multiple threads
            simultaneously, this method may attempt to read the file descriptor when no
            data is available. It may return zero events, or block until more events
            arrive (regardless of the requested timeout), or in the case that the
            :func:`~inotify_simple.INotify` object was instantiated with
            ``nonblocking=True``, raise ``BlockingIOError``.
        """
        data = self._readall()
        if not data and timeout != 0 and self._poller.poll(timeout):
            if read_delay is not None:
                sleep(read_delay / 1000.0)
            data = self._readall()
        return parse_events(data)

    def _readall(self):
        bytes_avail = c_int()
        ioctl(self, FIONREAD, bytes_avail)
        if not bytes_avail.value:
            return b''
        return read(self.fileno(), bytes_avail.value)


def parse_events(data):
    """Unpack data read from an inotify file descriptor into
    :attr:`~inotify_simple.Event` namedtuples (wd, mask, cookie, name). This function
    can be used if the application has read raw data from the inotify file
    descriptor rather than calling :func:`~inotify_simple.INotify.read`.

    Args:
        data (bytes): A bytestring as read from an inotify file descriptor.

    Returns:
        list: list of :attr:`~inotify_simple.Event` namedtuples"""
    pos = 0
    events = []
    while pos < len(data):
        wd, mask, cookie, namesize = unpack_from(_EVENT_FMT, data, pos)
        pos += _EVENT_SIZE + namesize
        name = data[pos - namesize : pos].split(b'\x00', 1)[0]
        events.append(Event(wd, mask, cookie, name if PY2 else fsdecode(name)))
    return events


class flags(IntEnum):
    """Inotify flags as defined in ``inotify.h`` but with ``IN_`` prefix omitted.
    Includes a convenience method :func:`~inotify_simple.flags.from_mask` for extracting
    flags from a mask."""
    ACCESS = 0x00000001  #: File was accessed
    MODIFY = 0x00000002  #: File was modified
    ATTRIB = 0x00000004  #: Metadata changed
    CLOSE_WRITE = 0x00000008  #: Writable file was closed
    CLOSE_NOWRITE = 0x00000010  #: Unwritable file closed
    OPEN = 0x00000020  #: File was opened
    MOVED_FROM = 0x00000040  #: File was moved from X
    MOVED_TO = 0x00000080  #: File was moved to Y
    CREATE = 0x00000100  #: Subfile was created
    DELETE = 0x00000200  #: Subfile was deleted
    DELETE_SELF = 0x00000400  #: Self was deleted
    MOVE_SELF = 0x00000800  #: Self was moved

    UNMOUNT = 0x00002000  #: Backing fs was unmounted
    Q_OVERFLOW = 0x00004000  #: Event queue overflowed
    IGNORED = 0x00008000  #: File was ignored

    ONLYDIR = 0x01000000  #: only watch the path if it is a directory
    DONT_FOLLOW = 0x02000000  #: don't follow a sym link
    EXCL_UNLINK = 0x04000000  #: exclude events on unlinked objects
    MASK_ADD = 0x20000000  #: add to the mask of an already existing watch
    ISDIR = 0x40000000  #: event occurred against dir
    ONESHOT = 0x80000000  #: only send event once

    @classmethod
    def from_mask(cls, mask):
        """Convenience method that returns a list of every flag in a mask."""
        return [flag for flag in cls.__members__.values() if flag & mask]


class masks(IntEnum):
    """Convenience masks as defined in ``inotify.h`` but with ``IN_`` prefix omitted."""
    #: helper event mask equal to ``flags.CLOSE_WRITE | flags.CLOSE_NOWRITE``
    CLOSE = flags.CLOSE_WRITE | flags.CLOSE_NOWRITE
    #: helper event mask equal to ``flags.MOVED_FROM | flags.MOVED_TO``
    MOVE = flags.MOVED_FROM | flags.MOVED_TO

    #: bitwise-OR of all the events that can be passed to
    #: :func:`~inotify_simple.INotify.add_watch`
    ALL_EVENTS  = (flags.ACCESS | flags.MODIFY | flags.ATTRIB | flags.CLOSE_WRITE |
        flags.CLOSE_NOWRITE | flags.OPEN | flags.MOVED_FROM | flags.MOVED_TO |
        flags.CREATE | flags.DELETE| flags.DELETE_SELF | flags.MOVE_SELF)
'''

# https://stackoverflow.com/a/53080237
inotify_simple: Any = importlib.util.module_from_spec(
    importlib.util.spec_from_loader("inotify_simple", loader=None),
)
sys.modules["inotify_simple"] = inotify_simple
exec(_inotify_simple_source, inotify_simple.__dict__)  # pylint: disable=exec-used


if __name__ == "__main__":
    main(sys.argv)
