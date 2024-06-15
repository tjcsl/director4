# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
import time
from typing import Any, Dict, Union

import docker
import websockets
from docker.models.services import Service
from websockets import client as client

from ..docker.services import get_director_service_name, get_service_by_name
from ..docker.utils import create_client
from ..files import check_run_sh_exists
from ..logs import DirectorSiteLogFollower
from .utils import mainloop_auto_cancel, wait_for_event


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
    websock: client.WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
) -> None:
    client = create_client()

    site_id = int(params["site_id"])

    service: Service = get_service_by_name(client, get_director_service_name(site_id))

    if service is None:
        await websock.close()
        return

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

        await mainloop_auto_cancel(
            [websock.wait_closed(), log_loop(log_follower), wait_for_event(stop_event)],
        )

    await websock.close()


async def multi_status_handler(  # pylint: disable=unused-argument
    websock: client.WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
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

    try:
        for site_id in services:
            log_followers[site_id] = DirectorSiteLogFollower(client, site_id)
            await log_followers[site_id].start(since_time=time.time())
            asyncio.ensure_future(wait_and_send_status(site_id, 0.0))

        log_coros = [
            log_loop(site_id, log_follower) for site_id, log_follower in log_followers.items()
        ]

        await mainloop_auto_cancel([websock.wait_closed(), *log_coros, wait_for_event(stop_event)])
    finally:
        for log_follower in log_followers.values():
            await log_follower.stop()

    await websock.close()
