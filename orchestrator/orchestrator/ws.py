import argparse
import asyncio
import json
import logging
import re
import signal
import ssl
import sys
import time
from typing import Any, Dict, Generator, List, Optional, Union, cast

import websockets
from docker.models.services import Service

from .docker.services import get_director_service_name, get_service_by_name
from .docker.utils import create_client
from .terminal import TerminalContainer

logger = logging.getLogger(__name__)


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
    site_id = int(params["site_id"])
    try:
        site_data = json.loads(await websock.recv())
        await websock.send(json.dumps({"connected": True}))
    except websockets.exceptions.ConnectionClosed:
        logger.info("Websocket connection for site %s terminal closed early", site_id)
        return

    logger.info("Opening terminal for site %s", site_id)

    client = create_client()

    terminal = TerminalContainer(client, site_id, site_data)
    await terminal.start()

    logger.info("Opened terminal for site %s", site_id)

    async def websock_loop() -> None:
        while True:
            try:
                frame = await websock.recv()
            except websockets.exceptions.ConnectionClosed:
                logger.info("Websocket connection for site %s terminal closed", site_id)
                await terminal.close()
                return

            if isinstance(frame, bytes):
                await terminal.write(frame)
            else:
                msg = json.loads(frame)

                if "size" in msg:
                    await terminal.resize(*msg["size"])
                elif "heartbeat" in msg:
                    await terminal.heartbeat()
                    # Send it back
                    try:
                        await websock.send(frame)
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("Websocket connection for site %s terminal closed", site_id)
                        await terminal.close()
                        return

    async def terminal_loop() -> None:
        while True:
            try:
                chunk = await terminal.read(4096)
            except OSError:
                chunk = b""

            if chunk == b"":
                logger.info("Terminal for site %s closed", site_id)
                await terminal.close()
                await websock.close()
                break

            try:
                await websock.send(chunk)
            except websockets.exceptions.ConnectionClosed:
                logger.info("Websocket connection for site %s terminal closed", site_id)
                await terminal.close()
                break

    await asyncio.wait(
        [websock_loop(), terminal_loop(), stop_event], return_when=asyncio.FIRST_COMPLETED,
    )

    await terminal.close()
    await websock.close()

    client.close()


async def status_handler(
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    client = create_client()

    site_id = int(params["site_id"])

    service = cast(Service, get_service_by_name(client, get_director_service_name(site_id)))
    assert service is not None

    # Interval between pings
    ping_interval = 30

    # When this interval expires without logs being sent, the log_generator will be recreated
    # and the status will be re-sent
    log_timeout = 60

    def create_log_generator(since_time: Union[int, float]) -> Generator[bytes, None, None]:
        return cast(
            Generator[bytes, None, None],
            service.logs(
                # Keep connection open to read logs
                follow=True,
                # Both stdout and stderr
                stdout=True,
                stderr=True,
                # No additional details
                details=False,
                timestamps=False,
                # And don't look at past logs.
                # You might think tail=0 would work from reading the documentation,
                # but in practice it has weird bugs.
                since=since_time,
                tail="all",
            ),
        )

    log_generator = create_log_generator(time.time())
    log_generator_creation_time = time.time()

    async def send_status() -> None:
        service.reload()

        data = {"running": False, "starting": False, "start_time": None}

        tasks = service.tasks()

        if any(task["Status"]["State"] == "running" for task in tasks):
            data["running"] = True

            # Date() in JavaScript can parse the default date format
            data["start_time"] = max(
                (
                    task["Status"]["Timestamp"]
                    for task in tasks
                    if task["Status"]["State"] == "running"
                ),
                default=None,
            )

        if any(
            # Not running, but supposed to be
            task["DesiredState"] in {"running", "ready"} and task["Status"]["State"] != "running"
            for task in tasks
        ):
            data["starting"] = True

        await websock.send(json.dumps(data))

    await send_status()

    log_generator_fut: Optional["asyncio.Future[bytes]"] = None

    last_ping_time = time.time()
    try:
        while True:
            if log_generator_fut is None:
                log_generator_fut = cast(
                    "asyncio.Future[bytes]",
                    asyncio.get_event_loop().run_in_executor(None, next, log_generator),
                )

            timeout = max(
                0,
                min(
                    log_timeout - (time.time() - log_generator_creation_time),
                    ping_interval - (time.time() - last_ping_time),
                ),
            )

            done, _ = await asyncio.wait(
                [log_generator_fut, stop_event],
                timeout=timeout,
                return_when=asyncio.FIRST_COMPLETED,
            )
            if stop_event in done:
                log_generator_fut.cancel()
                await websock.close()
                break
            elif log_generator_fut in done:
                line = await log_generator_fut
                if line.startswith(b"DIRECTOR: "):
                    await send_status()
                    await asyncio.sleep(1.0)
                    await send_status()

                log_generator_fut = None
            else:
                await websock.ping()
                last_ping_time = time.time()

            if (time.time() - log_generator_creation_time) > log_timeout:
                if log_generator_fut is not None:
                    log_generator_fut.cancel()
                    log_generator_fut = None

                log_generator = create_log_generator(time.time())
                log_generator_creation_time = time.time()
                await send_status()
    except websockets.exceptions.ConnectionClosed:
        if log_generator_fut is not None:
            log_generator_fut.cancel()
    finally:
        client.close()


async def route(websock: websockets.client.WebSocketClientProtocol, path: str) -> None:
    routes = [
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/terminal/?$"), terminal_handler),
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/status/?$"), status_handler),
    ]

    for route_re, handler in routes:
        match = route_re.match(path)
        if match is not None:
            params = {
                "REQUEST_PATH": path,
            }

            params.update(match.groupdict())

            await handler(websock, params)
            await websock.close()
            return


stop_event = asyncio.get_event_loop().create_future()


# https://websockets.readthedocs.io/en/stable/deployment.html#graceful-shutdown
async def run_server(*args: Any, **kwargs: Any) -> None:
    async with websockets.serve(*args, **kwargs) as server:
        logger.info("Started server")
        await stop_event
        logger.info("Stopping server")
        server.close()
        await server.wait_closed()
        logger.info("Stopped server")


def sigint_handler() -> None:
    stop_event.set_result(None)
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

    loop.add_signal_handler(signal.SIGTERM, stop_event.set_result, None)
    loop.add_signal_handler(signal.SIGINT, sigint_handler)

    loop.run_until_complete(run_server(route, options.bind, options.port, ssl=ssl_context))


if __name__ == "__main__":
    main(sys.argv)
