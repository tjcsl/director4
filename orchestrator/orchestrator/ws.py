# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import argparse
import asyncio
import json
import logging
import re
import signal
import ssl
import sys
from typing import Any, Dict, List, Optional, Union

import websockets
from docker.models.services import Service

from .docker.images import build_custom_docker_image
from .docker.services import get_director_service_name, get_service_by_name
from .docker.utils import create_client
from .exceptions import OrchestratorActionError
from .files import check_run_sh_exists
from .logs import DirectorSiteLogFollower
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

    client = create_client(timeout=60)

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

    websock_task = asyncio.Task(websock_loop())
    terminal_task = asyncio.Task(terminal_loop())

    await asyncio.wait(
        [websock_task, terminal_task, stop_event], return_when=asyncio.FIRST_COMPLETED,
    )

    await terminal.close()
    await websock.close()

    if not websock_task.done():
        websock_task.cancel()
        await websock_task

    if not terminal_task.done():
        terminal_task.cancel()
        await terminal_task

    client.close()


def serialize_service_status(site_id: int, service: Service) -> Dict[str, Any]:
    data = {
        "running": False,
        "starting": False,
        "start_time": None,
        "run_sh_exists": check_run_sh_exists(site_id),
    }

    tasks = service.tasks()

    if any(task["Status"]["State"] == "running" for task in tasks):
        data["running"] = True

        # Date() in JavaScript can parse the default date format
        data["start_time"] = max(
            (task["Status"]["Timestamp"] for task in tasks if task["Status"]["State"] == "running"),
            default=None,
        )

    if any(
        # Not running, but supposed to be
        task["DesiredState"] in {"running", "ready"} and task["Status"]["State"] != "running"
        for task in tasks
    ):
        data["starting"] = True

    return data


async def status_handler(
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    client = create_client()

    site_id = int(params["site_id"])

    service: Service = get_service_by_name(client, get_director_service_name(site_id))

    async def ping_loop() -> None:  # type: ignore
        while True:
            try:
                await websock.ping()
                await asyncio.sleep(30)
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                break

    async def log_loop(log_follower: DirectorSiteLogFollower) -> None:
        try:
            async for line in log_follower.iter_lines():
                if not line:
                    break

                if line.startswith("DIRECTOR: "):
                    service.reload()

                    await websock.send(json.dumps(serialize_service_status(site_id, service)))
                    asyncio.ensure_future(wait_and_send_status(1.0))
                    asyncio.ensure_future(wait_and_send_status(10.0))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass

    async def wait_and_send_status(duration: Union[int, float]) -> None:
        try:
            await asyncio.sleep(duration)
            await websock.send(json.dumps(serialize_service_status(site_id, service)))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass

    async with DirectorSiteLogFollower(client, site_id) as log_follower:
        try:
            await websock.send(json.dumps(serialize_service_status(site_id, service)))
        except websockets.exceptions.ConnectionClosed:
            return

        ping_task = asyncio.Task(ping_loop())
        wait_closed_task = asyncio.Task(websock.wait_closed())
        log_task = asyncio.Task(log_loop(log_follower))

        await asyncio.wait(
            [ping_task, wait_closed_task, log_task, stop_event],  # type: ignore
            return_when=asyncio.FIRST_COMPLETED,
        )

        if not wait_closed_task.done():
            wait_closed_task.cancel()
            await wait_closed_task

        if not ping_task.done():
            ping_task.cancel()
            await ping_task

        if not log_task:
            log_task.cancel()
            await log_task

    await websock.close()


async def build_image_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    try:
        build_data = json.loads(await websock.recv())
    except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError, asyncio.CancelledError):
        return

    client = await asyncio.get_event_loop().run_in_executor(None, create_client)

    try:
        await asyncio.get_event_loop().run_in_executor(
            None, build_custom_docker_image, client, build_data,
        )
    except OrchestratorActionError as ex:
        logger.error(
            "Error building image %s: %s: %s", build_data["name"], ex.__class__.__name__, ex,
        )
        result = {"successful": False, "msg": str(ex)}
    except BaseException as ex:  # pylint: disable=broad-except
        logger.error(
            "Error building image %s: %s: %s", build_data["name"], ex.__class__.__name__, ex,
        )
        result = {"successful": False, "msg": "Error"}
    else:
        logger.info("Built image %s", build_data["name"])
        result = {"successful": True, "msg": "Success"}

    try:
        await websock.send(json.dumps(result))
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        pass


async def route(websock: websockets.client.WebSocketClientProtocol, path: str) -> None:
    routes = [
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/terminal/?$"), terminal_handler),
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/status/?$"), status_handler),
        (re.compile(r"^/ws/sites/build-docker-image/?$"), build_image_handler),
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
