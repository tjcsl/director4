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
    client_sent_message = False
    forwarded_monitor_event = False

    logger.info(
        "File monitor websocket connected for site %s with params %s",
        site_id,
        params,
    )

    monitor = SiteFilesMonitor(site_id)
    try:
        await monitor.start()
    except Exception:  # pylint: disable=broad-except
        logger.exception("Failed to start file monitor for site %s", site_id)
        await websock.close()
        return
    logger.info("File monitor helper startup completed for site %s", site_id)

    async def log_monitor_exit() -> None:
        try:
            returncode = await monitor.wait()
            stderr = await monitor.read_stderr()
        except Exception:  # pylint: disable=broad-except
            logger.exception("Failed to inspect file monitor exit for site %s", site_id)
            return

        if returncode != 0:
            logger.error(
                "File monitor for site %s exited with code %s: %s",
                site_id,
                returncode,
                stderr.strip() or "<no stderr>",
            )
        else:
            logger.warning(
                "File monitor for site %s exited cleanly (client_sent_message=%s, forwarded_monitor_event=%s)",
                site_id,
                client_sent_message,
                forwarded_monitor_event,
            )

    monitor_exit_task = asyncio.create_task(log_monitor_exit())

    async def websock_loop() -> None:
        nonlocal client_sent_message
        while True:
            try:
                frame = await websock.recv()
            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "File monitor websocket closed by client for site %s before next frame (client_sent_message=%s, forwarded_monitor_event=%s)",
                    site_id,
                    client_sent_message,
                    forwarded_monitor_event,
                )
                return

            client_sent_message = True
            logger.info(
                "Received file monitor websocket frame for site %s: %s",
                site_id,
                frame[:300] if isinstance(frame, str) else "<binary>",
            )
            if isinstance(frame, str):
                msg = json.loads(frame)
                if not isinstance(msg, dict):
                    logger.warning(
                        "Ignoring non-dict file monitor payload for site %s: %r",
                        site_id,
                        msg,
                    )
                    continue

                if "action" in msg and "path" in msg:
                    if msg["action"] == "add":
                        logger.info(
                            "Handling file monitor add request for site %s path %r",
                            site_id,
                            msg["path"],
                        )
                        await monitor.add_watch(msg["path"])
                    elif msg["action"] == "remove":
                        logger.info(
                            "Handling file monitor remove request for site %s path %r",
                            site_id,
                            msg["path"],
                        )
                        await monitor.rm_watch(msg["path"])
                    else:
                        logger.warning(
                            "Ignoring unknown file monitor action for site %s: %r",
                            site_id,
                            msg["action"],
                        )
                elif "heartbeat" in msg:
                    logger.info("Echoing file monitor heartbeat for site %s", site_id)
                    # Send it back
                    try:
                        await websock.send(frame)
                    except websockets.exceptions.ConnectionClosed:
                        logger.warning(
                            "File monitor websocket closed while echoing heartbeat for site %s",
                            site_id,
                        )
                        return
                else:
                    logger.warning(
                        "Ignoring unexpected file monitor message shape for site %s: %r",
                        site_id,
                        msg,
                    )
            else:
                logger.warning("Ignoring binary file monitor frame for site %s", site_id)

    async def monitor_loop() -> None:
        nonlocal forwarded_monitor_event
        async for event in monitor.aiter_events():
            forwarded_monitor_event = True
            logger.info("Forwarding file monitor event for site %s: %r", site_id, event)
            try:
                await websock.send(json.dumps(event))
            except websockets.exceptions.ConnectionClosed:
                logger.warning(
                    "File monitor websocket closed while forwarding event for site %s",
                    site_id,
                )
                break
        logger.info(
            "File monitor event loop ended for site %s (client_sent_message=%s, forwarded_monitor_event=%s)",
            site_id,
            client_sent_message,
            forwarded_monitor_event,
        )

    logger.info("Entering file monitor mainloop for site %s", site_id)
    await mainloop_auto_cancel([websock_loop(), monitor_loop(), wait_for_event(stop_event)])
    logger.info(
        "File monitor mainloop completed for site %s (client_sent_message=%s, forwarded_monitor_event=%s, stop_event_set=%s)",
        site_id,
        client_sent_message,
        forwarded_monitor_event,
        stop_event.is_set(),
    )

    logger.info("Closing file monitor websocket for site %s", site_id)
    await websock.close()
    logger.info("Waiting for file monitor helper shutdown for site %s", site_id)
    await monitor.stop_wait(timeout=3)
    await asyncio.gather(monitor_exit_task, return_exceptions=True)
    logger.info("Finished file monitor handler cleanup for site %s", site_id)


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
