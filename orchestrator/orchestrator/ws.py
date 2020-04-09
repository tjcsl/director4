# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import argparse
import asyncio
import concurrent.futures
import json
import logging
import os
import re
import signal
import ssl
import sys
import time
from typing import Any, Dict, List, Optional, Union

import docker
import websockets
from docker.models.services import Service

from .docker.images import build_custom_docker_image, push_custom_docker_image
from .docker.services import get_director_service_name, get_service_by_name
from .docker.utils import create_client
from .exceptions import OrchestratorActionError
from .files import SiteFilesMonitor, check_run_sh_exists
from .logs import DirectorSiteLogFollower
from .terminal import TerminalContainer

logger = logging.getLogger(__name__)

# Long-running tasks like building/pushing images run in a separate executor so they don't hold up other
# tasks
long_running_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=min(32, (os.cpu_count() or 2) * 2)
)


def create_ssl_context(options: argparse.Namespace) -> Optional[ssl.SSLContext]:
    if options.ssl_certfile is None:
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    context.load_verify_locations(cafile=options.ssl_cafile)

    context.load_cert_chain(
        certfile=options.ssl_certfile, keyfile=options.ssl_keyfile,
    )

    return context


async def cancel_remaining_tasks(tasks: List["asyncio.Task[Any]"]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, concurrent.futures.CancelledError):
                pass


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

    try:
        terminal = TerminalContainer(client, site_id, site_data)
        await terminal.start()
    except docker.errors.APIError as ex:
        logger.error("Error opening terminal for site %d: %s", site_id, ex)
        return

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

    await cancel_remaining_tasks([websock_task, terminal_task])

    client.close()


async def file_monitor_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    site_id = int(params["site_id"])

    monitor = SiteFilesMonitor(site_id)
    await monitor.start()

    async def websock_loop() -> None:
        while True:
            try:
                frame = await websock.recv()
            except websockets.exceptions.ConnectionClosed:
                return

            if isinstance(frame, str):
                msg = json.loads(frame)
                if not isinstance(msg, dict):
                    continue

                if "action" in msg and "path" in msg:
                    if msg["action"] == "add":
                        await monitor.add_watch(msg["path"])
                    elif msg["action"] == "remove":
                        await monitor.rm_watch(msg["path"])
                elif "heartbeat" in msg:
                    # Send it back
                    try:
                        await websock.send(frame)
                    except websockets.exceptions.ConnectionClosed:
                        return

    async def monitor_loop() -> None:
        async for event in monitor.aiter_events():
            try:
                await websock.send(json.dumps(event))
            except websockets.exceptions.ConnectionClosed:
                break

    websock_task = asyncio.Task(websock_loop())
    monitor_task = asyncio.Task(monitor_loop())

    await asyncio.wait(
        [websock_task, monitor_task, stop_event], return_when=asyncio.FIRST_COMPLETED,
    )

    await websock.close()
    await monitor.stop_wait(timeout=3)

    await cancel_remaining_tasks([websock_task, monitor_task])


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

    if service is None:
        await websock.close()
        return

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
        except docker.errors.NotFound:
            pass

    async def wait_and_send_status(duration: Union[int, float]) -> None:
        try:
            await asyncio.sleep(duration)
            await websock.send(json.dumps(serialize_service_status(site_id, service)))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass

    async with DirectorSiteLogFollower(client, site_id) as log_follower:
        await log_follower.start(since_time=time.time())

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

        await cancel_remaining_tasks([wait_closed_task, ping_task, log_task])

    await websock.close()


async def logs_handler(
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    client = create_client()

    site_id = int(params["site_id"])

    service: Service = get_service_by_name(client, get_director_service_name(site_id))

    if service is None:
        await websock.close()
        return

    async def echo_loop() -> None:
        while True:
            try:
                msg = json.loads(await websock.recv())
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                break

            if isinstance(msg, dict) and "heartbeat" in msg:
                try:
                    await websock.send(json.dumps(msg))
                except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                    break

    async def log_loop(log_follower: DirectorSiteLogFollower) -> None:
        try:
            async for line in log_follower.iter_lines():
                if not line:
                    break

                await websock.send(json.dumps({"line": line}))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass

    async with DirectorSiteLogFollower(client, site_id) as log_follower:
        await log_follower.start(last_n=10)

        echo_task = asyncio.Task(echo_loop())
        log_task = asyncio.Task(log_loop(log_follower))

        await asyncio.wait(
            [echo_task, log_task, stop_event], return_when=asyncio.FIRST_COMPLETED,
        )

        await cancel_remaining_tasks([echo_task, log_task])

    await websock.close()


async def multi_status_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    client = create_client()

    try:
        site_ids = json.loads(await websock.recv())
    except websockets.exceptions.ConnectionClosed:
        return

    services: Dict[int, Service] = {}
    for site_id in site_ids:
        services[site_id] = get_service_by_name(client, get_director_service_name(site_id))

        if services[site_id] is None:
            await websock.close()
            return

    async def ping_loop() -> None:  # type: ignore
        while True:
            try:
                await websock.ping()
                await asyncio.sleep(30)
            except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
                break

    async def log_loop(site_id: int, log_follower: DirectorSiteLogFollower) -> None:
        try:
            async for line in log_follower.iter_lines():
                if not line:
                    break

                if line.startswith("DIRECTOR: "):
                    services[site_id].reload()

                    asyncio.ensure_future(wait_and_send_status(site_id, 0.0))
                    asyncio.ensure_future(wait_and_send_status(site_id, 1.0))
                    asyncio.ensure_future(wait_and_send_status(site_id, 10.0))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass
        except docker.errors.NotFound:
            pass

    async def wait_and_send_status(site_id: int, duration: Union[int, float]) -> None:
        try:
            await asyncio.sleep(duration)
            await websock.send(
                json.dumps(
                    {
                        "site_id": site_id,
                        "status": serialize_service_status(site_id, services[site_id]),
                    }
                )
            )
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass

    log_followers: Dict[int, DirectorSiteLogFollower] = {}

    for site_id in services:
        log_followers[site_id] = DirectorSiteLogFollower(client, site_id)
        await log_followers[site_id].start(since_time=time.time())
        asyncio.ensure_future(wait_and_send_status(site_id, 0.0))

    try:
        ping_task = asyncio.Task(ping_loop())
        wait_closed_task = asyncio.Task(websock.wait_closed())
        log_tasks = [
            asyncio.Task(log_loop(site_id, log_follower))
            for site_id, log_follower in log_followers.items()
        ]

        await asyncio.wait(
            [ping_task, wait_closed_task, *log_tasks, stop_event],  # type: ignore
            return_when=asyncio.FIRST_COMPLETED,
        )

        await cancel_remaining_tasks([wait_closed_task, ping_task, *log_tasks])
    finally:
        for log_follower in log_followers.values():
            await log_follower.stop()

    await websock.close()


async def build_image_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol, params: Dict[str, Any],
) -> None:
    try:
        build_data = json.loads(await websock.recv())
    except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError, asyncio.CancelledError):
        return

    client = await asyncio.get_event_loop().run_in_executor(None, create_client)

    result = {"successful": True, "msg": "Success"}

    try:
        await asyncio.get_event_loop().run_in_executor(
            long_running_executor, build_custom_docker_image, client, build_data,
        )
    except OrchestratorActionError as ex:
        logger.error(
            "Error building image %s: %s: %s", build_data["name"], ex.__class__.__name__, ex,
        )
        result = {"successful": False, "msg": "Error building image: {}".format(ex)}
    except BaseException as ex:  # pylint: disable=broad-except
        logger.error(
            "Error building image %s: %s: %s", build_data["name"], ex.__class__.__name__, ex,
        )
        result = {"successful": False, "msg": "Error building image"}
    else:
        logger.info("Built image %s", build_data["name"])

    try:
        await websock.send(json.dumps(result))
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        pass

    if result["successful"]:
        try:
            output = await asyncio.get_event_loop().run_in_executor(
                long_running_executor, push_custom_docker_image, client, build_data["name"],
            )

            logger.info("Pushed image %s", build_data["name"])
            logger.info("Output from pushing image %s: %s", build_data["name"], output)
        except OrchestratorActionError as ex:
            logger.error(
                "Error pushing image %s: %s: %s", build_data["name"], ex.__class__.__name__, ex,
            )
            result = {"successful": False, "msg": "Error pushing image: {}".format(ex)}
        except BaseException as ex:  # pylint: disable=broad-except
            logger.error(
                "Error pushing image %s: %s: %s", build_data["name"], ex.__class__.__name__, ex,
            )
            result = {"successful": False, "msg": "Error pushing image"}
        else:
            logger.info("Pushed image %s", build_data["name"])

        try:
            await websock.send(json.dumps(result))
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass


async def route(websock: websockets.client.WebSocketClientProtocol, path: str) -> None:
    routes = [
        (re.compile(r"^/ws/sites/(?P<site_id>\d+)/terminal/?$"), terminal_handler),
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

    loop.set_default_executor(
        concurrent.futures.ThreadPoolExecutor(max_workers=min(32, (os.cpu_count() or 2) * 3))
    )

    loop.run_until_complete(run_server(route, options.bind, options.port, ssl=ssl_context))


if __name__ == "__main__":
    main(sys.argv)
