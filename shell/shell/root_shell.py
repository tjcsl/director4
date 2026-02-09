# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import logging
from typing import Any, Mapping, Optional, Tuple, Union

import asyncssh

logger = logging.getLogger(__name__)


class RootShellSession(asyncssh.SSHServerSession[Any]):
    def __init__(self) -> None:
        self.chan: Optional[asyncssh.SSHServerChannel[Any]] = None
        self.request_type: Optional[str] = None
        self.remote_addr: Optional[str] = None

        self.buf = ""

    def connection_made(self, chan: asyncssh.SSHServerChannel[Any]) -> None:
        self.chan = chan

        addr, port = self.chan.get_extra_info("peername", ("<unknown>", 0))
        self.remote_addr = (
            "[{}]:{}".format(addr, port) if ":" in addr else "{}:{}".format(addr, port)
        )

    def connection_lost(self, exc: Optional[Exception]) -> None:
        logger.info("%s disconnected", self.remote_addr)

    def exec_requested(self, command: str) -> bool:
        logger.info("%s Requested command: %r", self.remote_addr, command)

        command_name, *command_args = command.split()

        if command_name in {"bash", "zsh", "sh"} and not command_args:
            self.request_type = "shell"
        else:
            self.write_stderr("Command not found: {}\r\n".format(command_name))
            self.request_type = "exec"

        return True

    def subsystem_requested(self, subsystem: str) -> bool:
        return True

    def pty_requested(
        self,
        term_type: Optional[str],
        term_size: Tuple[int, int, int, int],
        term_modes: Mapping[int, int],
    ) -> bool:
        logger.info(
            "%s Requested PTY: %r %r %r", self.remote_addr, term_type, term_size, term_modes
        )
        return True

    def shell_requested(self) -> bool:
        logger.info("%s Requested shell", self.remote_addr)
        self.request_type = "shell"
        return True

    def session_started(self) -> None:
        if self.request_type == "shell":
            self.write("# ")
        elif self.request_type == "exec":
            assert self.chan is not None
            self.chan.close()

    def data_received(self, data: Union[str, bytes], datatype: Any) -> None:
        if isinstance(data, bytes):
            data = data.decode("latin-1")

        self.buf += data

        if self.request_type == "shell":
            if "\n" in self.buf:
                command, self.buf = self.buf.split("\n", 1)

                logger.info("%s Typed command: %r", self.remote_addr, command)
                if command:
                    self.write_stderr("sh: Command not found: {}\r\n".format(command.split()[0]))

                self.write("# ")

    def break_received(self, msec: int) -> bool:
        self.write_stderr("^C")
        self.write("\n# ")

        assert self.chan is not None
        if hasattr(self.chan, "clear_input"):
            self.chan.clear_input()

        return True

    def signal_received(self, signal: Any) -> None:
        logger.info("%s Signal received: %r", self.remote_addr, signal)

    def terminal_size_changed(
        self,
        width: int,
        height: int,
        pixwidth: Optional[int] = None,
        pixheight: Optional[int] = None,
    ) -> None:
        logger.info(
            "%s Terminal size changed: %r", self.remote_addr, (width, height, pixwidth, pixheight)
        )

    def eof_received(self) -> bool:
        assert self.chan is not None
        self.chan.close()
        return False

    def soft_eof_received(self) -> None:
        assert self.chan is not None
        self.chan.close()

    def write(self, data: str) -> None:
        assert self.chan is not None

        if self.chan.get_encoding()[0] is None:
            self.chan.write(data.encode("latin-1"))
        else:
            self.chan.write(data)

    def write_stderr(self, data: str) -> None:
        assert self.chan is not None

        if self.chan.get_encoding()[0] is None:
            self.chan.write_stderr(data.encode("latin-1"))
        else:
            self.chan.write_stderr(data)
