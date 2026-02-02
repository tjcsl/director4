# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Dict

import websockets

from ..files import (
    SiteFilesMonitor,
    SiteFilesUserViewableException,
    remove_all_site_files_dangerous,
)
from ..websockets_types import WebSocketClientProtocol
from .utils import mainloop_auto_cancel, wait_for_event

logger = logging.getLogger(__name__)


async def file_monitor_handler(  # pylint: disable=unused-argument
    websock: WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
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

    await mainloop_auto_cancel([websock_loop(), monitor_loop(), wait_for_event(stop_event)])

    await websock.close()
    await monitor.stop_wait(timeout=3)


async def remove_all_site_files_dangerous_handler(  # pylint: disable=unused-argument
    websock: WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
) -> None:
    site_id = int(params["site_id"])

    try:
        await remove_all_site_files_dangerous(site_id)
    except SiteFilesUserViewableException as ex:
        logger.error("Error removing site files: %s: %s", ex.__class__.__name__, ex)
        result = {"successful": False, "msg": str(ex)}
    except Exception as ex:  # pylint: disable=broad-except
        logger.error("Error removing site files: %s: %s", ex.__class__.__name__, ex)
        result = {"successful": False, "msg": "Error"}
    else:
        result = {"successful": True, "msg": "Success"}

    try:
        await websock.send(json.dumps(result))
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        pass
