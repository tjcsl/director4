# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from __future__ import annotations

import asyncio
import json
from typing import Any, Dict

import websockets
from docker.models.services import Service

from ..docker.services import get_director_service_name, get_service_by_name
from ..docker.utils import create_client
from ..logs import DirectorSiteLogFollower
from ..websockets_types import WebSocketClientProtocol
from .utils import mainloop_auto_cancel, wait_for_event


async def logs_handler(
    websock: WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
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

        await mainloop_auto_cancel(
            [echo_loop(), log_loop(log_follower), wait_for_event(stop_event)]
        )

    await websock.close()
