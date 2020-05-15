# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
import logging
from typing import Any, Dict

import docker
import websockets

from .. import settings
from ..docker.utils import create_client
from ..terminal import TerminalContainer
from .utils import mainloop_auto_cancel, wait_for_event

logger = logging.getLogger(__name__)


async def web_terminal_handler(  # pylint: disable=unused-argument
    websock: websockets.client.WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
) -> None:
    site_id = int(params["site_id"])
    try:
        site_data = json.loads(await websock.recv())
        command = json.loads(await websock.recv())
        await websock.send(json.dumps({"connected": True}))
    except websockets.exceptions.ConnectionClosed:
        logger.info("Websocket connection for site %s terminal closed early", site_id)
        return

    logger.info("Opening terminal for site %s", site_id)

    client = create_client(timeout=60)

    try:
        terminal = TerminalContainer(client, site_id, site_data)
        await terminal.start(command=command)
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

    await mainloop_auto_cancel(
        [
            websock_loop(),
            terminal_loop(),
            wait_for_event(stop_event),
            asyncio.sleep(settings.SHELL_TERMINAL_MAX_LIFETIME),
        ]
    )

    await terminal.close()
    await websock.close()

    client.close()
