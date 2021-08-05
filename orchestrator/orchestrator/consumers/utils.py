# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import concurrent.futures
from typing import Any, Awaitable, Callable, Iterable, List, Optional, Union

import websockets
from websockets import client as client


async def ping_loop(
    websock: client.WebSocketClientProtocol,
    interval: Union[int, float],
) -> None:
    while True:
        try:
            await websock.ping()
            await asyncio.sleep(interval)
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass


async def websock_recv_devnull_loop(websock: client.WebSocketClientProtocol) -> None:
    while True:
        try:
            await websock.recv()
        except (websockets.exceptions.ConnectionClosed, asyncio.CancelledError):
            pass


async def cancel_remaining_tasks(
    tasks: List[Union["asyncio.Task[Any]", "asyncio.Future[Any]"]],
) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()

        try:
            await task
        except (asyncio.CancelledError, concurrent.futures.CancelledError):
            pass


async def mainloop_auto_cancel(
    awaitables: Iterable[Awaitable[None]],
    *,
    timeout: Union[int, float, None] = None,
    cleanup_callback: Optional[Callable[[], Awaitable[Any]]] = None,
) -> None:
    """Runs all the awaitables in ``awaitables`` concurrently. When one of them
    finishes, or when ``timeout`` expires, ``cleanup_callback`` is called
    if present and the tasks are cancelled.

    """

    tasks = [asyncio.ensure_future(awaitable) for awaitable in awaitables]

    await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED, timeout=timeout)

    try:
        if cleanup_callback is not None:
            await cleanup_callback()
    finally:
        await cancel_remaining_tasks(tasks)


async def wait_for_event(event: asyncio.Event) -> None:
    """Wraps asyncio.Event.wait(), but returns None.

    This is needed due to oddities of mypy's annotations for ``asyncio.wait()``
    and the code that waits for events.

    """
    await event.wait()
