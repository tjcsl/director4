# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
from typing import Any, Dict

import websockets

from ..files import SiteFilesMonitor
from .utils import mainloop_auto_cancel, wait_for_event


async def file_monitor_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol,
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
