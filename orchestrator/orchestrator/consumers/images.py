# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import concurrent.futures
import json
import logging
import os
from typing import Any, Dict, Iterator, Optional, TypeVar, cast

import websockets
from websockets import client as client

from ..docker.images import build_custom_docker_image, push_custom_docker_image
from ..docker.utils import create_client
from ..exceptions import OrchestratorActionError

logger = logging.getLogger(__name__)


# Run in a separate executor so we don't hold up other tasks
image_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=min(32, (os.cpu_count() or 2) * 2)
)

T = TypeVar("T")


def next_or_none(item_it: Iterator[T]) -> Optional[T]:
    try:
        return next(item_it)
    except StopIteration:
        return None


async def build_image_handler(  # pylint: disable=unused-argument
    websock: client.WebSocketClientProtocol,
    params: Dict[str, Any],
    stop_event: asyncio.Event,
) -> None:
    try:
        build_data = json.loads(await websock.recv())
    except (websockets.exceptions.ConnectionClosed, json.JSONDecodeError, asyncio.CancelledError):
        return

    client = await asyncio.get_event_loop().run_in_executor(image_executor, create_client)

    result = {"successful": True, "msg": "Success"}

    try:
        await asyncio.get_event_loop().run_in_executor(
            image_executor,
            build_custom_docker_image,
            client,
            build_data,
        )
    except OrchestratorActionError as ex:
        logger.error(
            "Error building image %s: %s: %s",
            build_data["name"],
            ex.__class__.__name__,
            ex,
        )
        result = {"successful": False, "msg": "Error building image: {}".format(ex)}
    except BaseException as ex:  # pylint: disable=broad-except
        logger.error(
            "Error building image %s: %s: %s",
            build_data["name"],
            ex.__class__.__name__,
            ex,
        )
        result = {"successful": False, "msg": "Error building image"}
    else:
        logger.info("Built image %s", build_data["name"])

    if result["successful"]:
        try:
            logger.info("Pushing image %s", build_data["name"])

            output_generator = await asyncio.get_event_loop().run_in_executor(
                image_executor,
                push_custom_docker_image,
                client,
                build_data["name"],
            )

            failed = False
            while True:
                data = cast(
                    Optional[Dict[str, str]],
                    await asyncio.get_event_loop().run_in_executor(
                        image_executor, next_or_none, output_generator
                    ),
                )

                if data is None:
                    break

                logger.info("Output from pushing image %s: %s", build_data["name"], data)

                if "errorDetail" in data:
                    failed = True

        except OrchestratorActionError as ex:
            logger.error(
                "Error pushing image %s: %s: %s",
                build_data["name"],
                ex.__class__.__name__,
                ex,
            )
            result = {"successful": False, "msg": "Error pushing image: {}".format(ex)}
        except BaseException as ex:  # pylint: disable=broad-except
            logger.error(
                "Error pushing image %s: %s: %s",
                build_data["name"],
                ex.__class__.__name__,
                ex,
            )
            result = {"successful": False, "msg": "Error pushing image"}
        else:
            if failed:
                result = {"successful": False, "msg": "Error pushing image"}
                logger.info("Failed to push image %s", build_data["name"])
            else:
                logger.info("Pushed image %s", build_data["name"])

    try:
        await websock.send(json.dumps(result))
    except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
        pass
