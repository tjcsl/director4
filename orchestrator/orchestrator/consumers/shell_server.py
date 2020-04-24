# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import base64
import binascii
import json
import logging
import time
from typing import Any, Dict, cast

import docker
import websockets

from directorutil import crypto

from .. import settings
from ..docker.utils import create_client
from ..terminal import TerminalContainer
from .utils import mainloop_auto_cancel, wait_for_event

logger = logging.getLogger(__name__)


class ShellTokenLoadError(Exception):
    pass


class ShellTokenUserViewableLoadError(ShellTokenLoadError):
    pass


def load_token(token: bytes) -> Dict[str, Any]:
    try:
        encrypted_msg, signature = map(base64.b64decode, token.split())
    except TypeError as ex:
        raise ShellTokenLoadError("Invalid token format: {}".format(ex)) from ex
    except (binascii.Error, binascii.Incomplete) as ex:
        raise ShellTokenLoadError("Error lading base64 token data: {}".format(ex)) from ex

    try:
        crypto.verify_signature(
            msg=encrypted_msg,
            signature=signature,
            public_key=settings.SHELL_SIGNING_TOKEN_PUBLIC_KEY,
        )
    except crypto.DirectorCryptoVerifyError as ex:
        raise ShellTokenLoadError("Invalid token signature: {}".format(ex)) from ex
    except crypto.DirectorCryptoError as ex:
        raise ShellTokenLoadError("Error verifying token signature: {}".format(ex)) from ex

    try:
        decrypted_msg = crypto.decrypt_message(
            msg=encrypted_msg, private_key=settings.SHELL_ENCRYPTION_TOKEN_PRIVATE_KEY,
        )
    except crypto.DirectorCryptoError as ex:
        raise ShellTokenLoadError("Error decrypting token: {}".format(ex)) from ex

    try:
        site_data = cast(Dict[str, Any], json.loads(decrypted_msg.decode()))
    except json.JSONDecodeError as ex:
        raise ShellTokenLoadError("Error loading JSON: {}".format(ex)) from ex

    if time.time() >= site_data.get("token_expire_time", 0):
        raise ShellTokenUserViewableLoadError(
            "Token expired (you must select a site within 60 seconds)"
        )

    return site_data


async def ssh_shell_handler(
    websock: websockets.client.WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
) -> None:
    site_id = int(params["site_id"])
    try:
        token = await websock.recv()
    except websockets.exceptions.ConnectionClosed:
        return

    try:
        site_data = load_token(token.encode() if isinstance(token, str) else token)
    except ShellTokenUserViewableLoadError as ex:
        await websock.send(json.dumps({"connected": True}))
        await websock.send(b"\x01" + str(ex).encode() + b"\r\n")
        logger.error("Error loading token: %s", ex)
        return
    except ShellTokenLoadError as ex:
        logger.error("Error loading token: %s", ex)
        return

    if site_id != site_data["id"]:
        logger.error("Invalid site ID for opening SSH shell")
        return

    logger.info("Opening SSH shell for site %d", site_id)

    try:
        await websock.send(json.dumps({"connected": True}))
    except websockets.exceptions.ConnectionClosed:
        return

    client = create_client(timeout=60)

    try:
        terminal = TerminalContainer(client, site_id, site_data)
        await terminal.start()
    except docker.errors.APIError as ex:
        logger.error("Error opening SSH shell for site %d: %s", site_id, ex)
        return

    logger.info("Opened SSH shell for site %s", site_id)

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
                    size = msg.get("size")
                    if (
                        isinstance(size, list)
                        and len(size) == 2
                        and all(isinstance(x, int) for x in size)
                    ):
                        rows, cols = size
                        await terminal.resize(rows, cols)
                elif "heartbeat" in msg:
                    await terminal.heartbeat()
                    # Send it back
                    try:
                        await websock.send(frame)
                    except websockets.exceptions.ConnectionClosed:
                        logger.info("Websocket connection for site %s SSH shell closed", site_id)
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
                await websock.send(b"\0" + chunk)
            except websockets.exceptions.ConnectionClosed:
                logger.info("Websocket connection for site %s SSH shell closed", site_id)
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
