import asyncio
import multiprocessing
import time
import unittest

import asyncssh
from asyncssh import PermissionDenied

from ..main import main


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
        time.sleep(0.5)

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
