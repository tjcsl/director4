import asyncio
import multiprocessing
import socket
import time
import unittest

import asyncssh
from asyncssh import PermissionDenied

from ..main import main


def wait_for_port(host: str, port: int, process: multiprocessing.Process) -> None:
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if not process.is_alive():
            raise AssertionError("Shell server process exited before accepting connections")

        try:
            with socket.create_connection((host, port), timeout=0.1):
                return
        except OSError:
            time.sleep(0.1)

    raise AssertionError("Timed out waiting for shell server to accept connections")


class ShellTest(unittest.TestCase):
    def test_main(self) -> None:
        process = multiprocessing.Process(target=main, name="main", args=("m",))
        process.start()

        time.sleep(0.1)

        self.assertTrue(process.is_alive())

        process.terminate()
        process.join()

    def test_ssh_connection(self) -> None:
        process = multiprocessing.Process(target=main, name="main", args=("m",))
        process.start()
        wait_for_port("127.0.0.1", 2322, process)

        # Try to connect as "root"

        async def client_ls() -> None:
            async with asyncssh.connect(
                "127.0.0.1", port=2322, username="root", password="test", known_hosts=None
            ) as conn:
                await conn.run("ls")

        asyncio.run(client_ls())

        # Now, try to connect as "test" instead of "root"
        async def client() -> None:
            async with asyncssh.connect(
                "127.0.0.1", port=2322, username="test", password="test", known_hosts=None
            ) as conn:
                await conn.run("ls", check=True)

        with self.assertRaises(PermissionDenied):
            asyncio.run(client())

        process.terminate()
        process.join()
