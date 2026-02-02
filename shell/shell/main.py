# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import argparse
import asyncio
import concurrent.futures
import logging
import os
import signal
import sys
from typing import List

from . import settings
from .server import ShellSSHListener

logger = logging.getLogger(__package__)


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(prog=argv[0])

    parser.add_argument(
        "--server-host-key",
        dest="server_host_keys",
        nargs="+",
        action="append",
        default=[],
        help="The paths of one or more host keys to use. This overrides "
        "settings.SERVER_HOST_KEY_FILES if passed.",
    )
    parser.add_argument(
        "--extra-server-host-key",
        dest="extra_server_host_keys",
        nargs="+",
        action="append",
        default=[],
        help="The paths of one or more host keys to use. These will be used in addition to any "
        "keys specified with --server-host-key or settings.SERVER_HOST_KEY_FILES.",
    )
    parser.add_argument("-b", "--bind", dest="bind_host", default="127.0.0.1")
    parser.add_argument("-p", "--port", dest="bind_port", default=2322, type=int)

    options = parser.parse_args(argv[1:])

    if not options.server_host_keys:
        if not settings.SERVER_HOST_KEY_FILES and not options.extra_server_host_keys:
            sys.exit(
                "You must specify at least one server host key in settings.SERVER_HOST_KEY_FILES "
                "or using the --server-host-key or --extra-server-host-key arguments."
            )

        options.server_host_keys = settings.SERVER_HOST_KEY_FILES

    options.server_host_keys.extend(options.extra_server_host_keys)

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s: %(levelname)7s: %(message)s"))
    logger.addHandler(handler)

    async def run_server() -> None:
        stop_event = asyncio.Event()
        loop = asyncio.get_running_loop()

        def _signal_handler(sig: signal.Signals) -> None:
            stop_event.set()
            loop.remove_signal_handler(sig)

        loop.add_signal_handler(signal.SIGTERM, lambda: _signal_handler(signal.SIGTERM))
        loop.add_signal_handler(signal.SIGINT, lambda: _signal_handler(signal.SIGINT))

        loop.set_default_executor(
            concurrent.futures.ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 2) * 2))
        )

        listener = ShellSSHListener(
            bind_host=options.bind_host,
            bind_port=options.bind_port,
            server_host_keys=options.server_host_keys,
        )

        await listener.start()

        logger.info("Started server")
        await stop_event.wait()
        logger.info("Stopping server")
        listener.close()
        await listener.wait_closed()
        logger.info("Stopped server")

    asyncio.run(run_server())


if __name__ == "__main__":
    main(sys.argv)
