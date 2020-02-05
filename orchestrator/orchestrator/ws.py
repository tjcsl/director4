import argparse
import asyncio
import json
import re
import ssl
import sys
from typing import Any, Dict, List, Optional

import websockets

from .docker.utils import create_client
from .terminal import TerminalContainer


def create_ssl_context(options: argparse.Namespace) -> Optional[ssl.SSLContext]:
    if options.ssl_certfile is None:
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    context.load_verify_locations(cafile=options.ssl_cafile)

    context.load_cert_chain(
        certfile=options.ssl_certfile, keyfile=options.ssl_keyfile,
    )

    return context


async def terminal_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    try:
        info_frame = json.loads(await websock.recv())
    except websockets.exceptions.ConnectionClosed:
        return

    terminal = TerminalContainer(create_client(), info_frame["site_id"], info_frame["data"])

    await terminal.start_process()

    async def websock_loop() -> None:
        while True:
            try:
                frame = await websock.recv()
            except websockets.exceptions.ConnectionClosed:
                terminal.terminate()

                try:
                    await asyncio.wait_for(terminal.wait(), timeout=5)
                except asyncio.TimeoutError:
                    terminal.kill()
                    terminal.wait()

                return

            if isinstance(frame, bytes):
                terminal.write(frame)
            else:
                msg = json.loads(frame)

                if "size" in msg:
                    terminal.resize(*msg["size"])
                elif "heartbeat" in msg:
                    terminal.heartbeat()
                    # Send it back
                    await websock.send(frame)

    async def terminal_loop() -> None:
        while True:
            try:
                chunk = await terminal.read(4096)
            except OSError:
                chunk = b""

            if chunk == b"":
                await terminal.wait()
                await websock.close()
                break

            await websock.send(chunk)

    await asyncio.gather(websock_loop(), terminal_loop())


async def route(websock: websockets.client.WebSocketClientProtocol, path: str) -> None:
    routes = [
        (re.compile(r"^/ws/terminal/?$"), terminal_handler),
    ]

    for route_re, handler in routes:
        match = route_re.match(path)
        if match is not None:
            params = {
                "REQUEST_PATH": path,
            }

            params.update(match.groupdict())

            await handler(websock, params)


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

    loop = asyncio.get_event_loop()

    loop.run_until_complete(
        websockets.serve(route, options.bind, options.port, ssl=ssl_context)  # type: ignore
    )
    loop.run_forever()


if __name__ == "__main__":
    main(sys.argv)
