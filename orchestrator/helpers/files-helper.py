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
def get_new_mode(old_mode: int, mode_str: Optional[str]) -> int:
    if not mode_str:
        return old_mode
    elif set(mode_str) < set("01234567"):
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


def ensure_directories_exist_cmd(site_directory: str) -> None:
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

    try:
        update_mode(relpath, mode_str)
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


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

    try:
        os.makedirs(relpath, mode=get_new_mode(0o755, mode_str), exist_ok=False)
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def create_cmd(site_directory: str, relpath: str, mode_str: Optional[str] = None) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    try:
        # This combination of flags will make the call fail if the file already exists.
        fd = os.open(relpath, os.O_RDWR | os.O_CREAT | os.O_EXCL, get_new_mode(0o644, mode_str))
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)
    else:
        os.close(fd)


def rm_cmd(site_directory: str, relpath: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    try:
        if os.path.exists(relpath) or os.path.islink(relpath):
            os.remove(relpath)
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def rmdir_recur_cmd(site_directory: str, relpath: str) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    try:
        if os.path.isdir(relpath):
            shutil.rmtree(relpath)
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


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


def download_zip_cmd(
    site_directory: str, relpath: str, max_size_spec: str, max_files_spec: str,
) -> None:
    if relpath.startswith("/"):
        print("Invalid path", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    chroot_into(site_directory)

    max_size = int(max_size_spec)
    max_files = int(max_files_spec)

    zf = zipstream.ZipFile(compression=zipstream.ZIP_DEFLATED)

    try:
        for root, files, dirs in os.walk(relpath):
            short_root = os.path.relpath(root, relpath)
            if short_root == ".":
                short_root = ""

            for fname in files + dirs:
                fpath = os.path.join(root, fname)

                f_stat = os.stat(fpath, follow_symlinks=False)
                if (stat.S_ISREG(f_stat.st_mode) or stat.S_ISLNK(f_stat.st_mode)) and f_stat.st_size > max_size:
                    print("File {} too large".format(fpath), file=sys.stderr)
                    sys.exit(SPECIAL_EXIT_CODE)

                zf.write(
                    filename=fpath,
                    arcname=os.path.join(short_root, fname),
                )
    except OSError as ex:
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    try:
        for chunk in zf:
            sys.stdout.buffer.write(chunk)
            sys.stdout.flush()
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
        print(ex, file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)


def main(argv: List[str]) -> None:
    if len(argv) < 2:
        print("Please specify a command", file=sys.stderr)
        sys.exit(SPECIAL_EXIT_CODE)

    resource.setrlimit(resource.RLIMIT_AS, (200 * 1024 * 1024, 200 * 1024 * 1024))

    commands = {
        "ensure-directories-exist": (ensure_directories_exist_cmd, [1]),
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
        "create": (create_cmd, [2, 3]),
        "download-zip": (download_zip_cmd, [4]),
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


VENDOR_PREFIX = "ORCHESTRATOR_HELPER_VENDOR_"


class OrchestratorHelperVendorLoader:
    def load_module(self, fullname: str):
        try:
            return sys.modules[fullname]
        except KeyError:
            pass

        text = ""
        is_package = False
        for key in [VENDOR_PREFIX + fullname, VENDOR_PREFIX + fullname + ".__init__"]:
            if key in os.environ:
                text = os.environ[key]
                is_package = "." in key
                break
        else:
            raise ImportError

        # https://stackoverflow.com/a/53080237
        mod = importlib.util.module_from_spec(
            importlib.util.spec_from_loader(fullname, loader=self, is_package=is_package)
        )
        sys.modules[fullname] = mod

        exec(text, mod.__dict__)

        return mod


class OrchestratorHelperVendorFinder:
    def find_module(self, fullname: str, path=None):
        if (
            VENDOR_PREFIX + fullname in os.environ
            or VENDOR_PREFIX + fullname + ".__init__" in os.environ
        ):
            return OrchestratorHelperVendorLoader()
        return None


sys.meta_path.append(OrchestratorHelperVendorFinder())

import inotify_simple
import zipstream


if __name__ == "__main__":
    main(sys.argv)
