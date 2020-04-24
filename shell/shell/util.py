# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
from typing import Any, Awaitable, Callable, TypeVar

T = TypeVar("T")


def run_default_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> Awaitable[T]:
    def wrapper() -> T:
        return func(*args, **kwargs)

    return asyncio.get_event_loop().run_in_executor(None, wrapper)
