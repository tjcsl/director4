# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from __future__ import annotations

from typing import Any, Protocol


class WebSocketClientProtocol(Protocol):
    async def ping(self) -> Any: ...

    async def recv(self) -> Any: ...

    async def send(self, data: Any) -> Any: ...

    async def close(self) -> Any: ...

    async def wait_closed(self) -> Any: ...
