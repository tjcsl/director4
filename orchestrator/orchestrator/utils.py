# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Awaitable, Tuple, TypeVar

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
