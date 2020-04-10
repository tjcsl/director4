# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import concurrent.futures
import functools
from typing import Any, Awaitable, Callable, Coroutine, Generator, List, Optional, Tuple, TypeVar

T = TypeVar("T")
U = TypeVar("U")  # pylint: disable=invalid-name


async def add_const(awaitable: Awaitable[T], const: U) -> Tuple[T, U]:
    """Given an awaitable and a constant value, awaits the awaitable and returns a tuple of
    (awaitable return value, constant).

    Designed for use with asyncio.as_completed(), where you normally have no way of knowing which
    value came from which awaitable. With this helper, you can add a special value that will
    tell you where it came from.
    """
    return (await awaitable), const


def run_in_executor(
    executor: Optional[concurrent.futures.Executor],
) -> Callable[
    [Callable[..., T]], Callable[..., Coroutine[Any, Any, T]],
]:
    """A decorator for synchronous functions to make them into coroutines (async functions)
    that automatically run in the specified executor.

    Example:
    @run_in_executor(None)
    def test():
        print("Test")
    ...
    await test()

    """

    def wrap(func: Callable[..., T]) -> Callable[..., Coroutine[Any, Any, T]]:
        async def wrapper(*args: Any, **kwargs: Any) -> T:
            def callback() -> T:
                return func(*args, **kwargs)

            return await asyncio.get_event_loop().run_in_executor(executor, callback)

        functools.update_wrapper(wrapper, func)
        return wrapper

    return wrap


async def cancel_remaining_tasks(tasks: List["asyncio.Task[Any]"]) -> None:
    for task in tasks:
        if not task.done():
            task.cancel()
            try:
                await task
            except (asyncio.CancelledError, concurrent.futures.CancelledError):
                pass


async def wait_for_event(event: asyncio.Event) -> None:
    """Wraps asyncio.Event.wait(), but returns None.

    This is needed due to oddities of mypy's annotations for ``asyncio.wait()``
    and the code that waits for events.

    """
    await event.wait()


def iter_chunks(stream: Any, bufsize: int) -> Generator[bytes, None, None]:
    while True:
        chunk = stream.read(bufsize)
        if not chunk:
            break

        yield chunk
