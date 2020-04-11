# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import argparse
import asyncio
import concurrent.futures
import logging
import os
import re
import signal
import ssl
import sys
from typing import Any, Awaitable, Callable, Dict, List, Optional, Pattern, Tuple

import websockets

from .consumers import (
    build_image_handler,
    file_monitor_handler,
    logs_handler,
    multi_status_handler,
    status_handler,
    web_terminal_handler,
)

logger = logging.getLogger(__package__)  # Since this is run with "python -m orchestrator.ws"


def create_ssl_context(options: argparse.Namespace) -> Optional[ssl.SSLContext]:
    if options.ssl_certfile is None:
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    context.load_verify_locations(cafile=options.ssl_cafile)

    context.load_cert_chain(
        certfile=options.ssl_certfile, keyfile=options.ssl_keyfile,
    )

    return context


async def route(websock: websockets.client.WebSocketClientProtocol, path: str) -> None:
    routes: List[
        Tuple[
            Pattern[str],
            Callable[
                [websockets.client.WebSocketClientProtocol, Dict[str, Any], asyncio.Event],
                Awaitable[None],
            ],
        ]
    ] = [
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/terminal/?$"), web_terminal_handler),
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/status/?$"), status_handler),
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/files/monitor/?$"), file_monitor_handler),
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/logs/?$"), logs_handler),
        (re.compile(r"^/ws/sites/build-docker-image/?$"), build_image_handler),
        (re.compile(r"^/ws/sites/multi-status/?$"), multi_status_handler),
    ]

    for route_re, handler in routes:
        match = route_re.match(path)
        if match is not None:
            params = {
                "REQUEST_PATH": path,
            }

            params.update(match.groupdict())

            await handler(websock, params, stop_event)
            await websock.close()
            return


stop_event = asyncio.Event()


# https://websockets.readthedocs.io/en/stable/deployment.html#graceful-shutdown
async def run_server(*args: Any, **kwargs: Any) -> None:
    async with websockets.serve(*args, **kwargs) as server:
        logger.info("Started server")
        await stop_event.wait()
        logger.info("Stopping server")
        server.close()
        await server.wait_closed()
        logger.info("Stopped server")


def sigterm_handler() -> None:
    stop_event.set()
    asyncio.get_event_loop().remove_signal_handler(signal.SIGTERM)


def sigint_handler() -> None:
    stop_event.set()
    asyncio.get_event_loop().remove_signal_handler(signal.SIGINT)


def main(argv: List[str]) -> None:
    parser = argparse.ArgumentParser(prog=argv[0])

    parser.add_argument("-b", "--bind", dest="bind", default="localhost")
    parser.add_argument("-p", "--port", dest="port", default=5010, type=int)

    ssl_group = parser.add_argument_group("SSL")
    ssl_group.add_argument("--certfile", dest="ssl_certfile", default=None)
    ssl_group.add_argument("--keyfile", dest="ssl_keyfile", default=None)
    ssl_group.add_argument("--client-ca-file", dest="ssl_cafile", default=None)

    options = parser.parse_args(argv[1:])

    if options.ssl_certfile is None and (
        options.ssl_keyfile is not None or options.ssl_cafile is not None
    ):
        print("Cannot specify --keyfile or --client-ca-file without --certfile", file=sys.stderr)
        sys.exit(1)

    ssl_context = create_ssl_context(options)

    logger.setLevel(logging.INFO)

    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s: %(levelname)s: %(message)s"))
    logger.addHandler(handler)

    loop = asyncio.get_event_loop()

    loop.add_signal_handler(signal.SIGTERM, sigterm_handler)
    loop.add_signal_handler(signal.SIGINT, sigint_handler)

    loop.set_default_executor(
        concurrent.futures.ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 2) * 3))
    )

    loop.run_until_complete(run_server(route, options.bind, options.port, ssl=ssl_context))


if __name__ == "__main__":
    main(sys.argv)
