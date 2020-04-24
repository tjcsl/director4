# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import ssl
from typing import Any, Awaitable, Callable, Dict, Optional, TypeVar

T = TypeVar("T")


def run_default_executor(func: Callable[..., T], *args: Any, **kwargs: Any) -> Awaitable[T]:
    def wrapper() -> T:
        return func(*args, **kwargs)

    return asyncio.get_event_loop().run_in_executor(None, wrapper)


def create_ssl_context(ssl_settings: Optional[Dict[str, Any]]) -> Optional[ssl.SSLContext]:
    if ssl_settings is None:
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.verify_mode = ssl.CERT_REQUIRED
    context.load_verify_locations(cafile=ssl_settings["cafile"])

    client_certinfo = ssl_settings.get("client_cert", None)
    if client_certinfo is not None:
        context.load_cert_chain(
            certfile=ssl_settings["certfile"],
            keyfile=ssl_settings.get("keyfile"),
            password=lambda: ssl_settings["password"],  # type: ignore
        )

    return context
