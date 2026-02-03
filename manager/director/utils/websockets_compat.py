# SPDX-License-Identifier: MIT
# (c) 2026 The TJHSST Director 4.0 Development Team & Contributors

try:
    # websockets 12+ keeps the legacy API here.
    from websockets.legacy.client import Connect, WebSocketClientProtocol, connect
except ImportError:  # pragma: no cover - legacy module not present in older websockets
    from websockets.client import Connect, WebSocketClientProtocol, connect  # type: ignore

from websockets import exceptions

__all__ = [
    "Connect",
    "WebSocketClientProtocol",
    "connect",
    "exceptions",
]
