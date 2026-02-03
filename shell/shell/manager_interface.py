# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import http.client
import socket
import urllib.error
import urllib.parse
import urllib.request
from typing import Dict, Iterable, Optional, Sequence, Tuple, Union, cast

from . import settings


class ManagerRequestError(Exception):
    pass


def make_manager_request(
    path: str,
    *,
    method: str = "GET",
    params: Union[Dict[str, str], Sequence[Tuple[str, str]], None] = None,
    data: Union[bytes, Dict[str, str], Iterable[bytes], None] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Union[int, float] = 60,
) -> http.client.HTTPResponse:
    """Opens an HTTP request to the manager and return the raw HTTP response.

    Raises urllib.error.HTTPError on HTTP errors. Other errors are wrapped in a
    ManagerRequestError.

    Args:
        path: The path to request from the server. Should have a leading slash.
        method: The HTTP method to use (like GET or POST).
        data: An object specifying additional data to send to the server.
            This is passed directly to urllib.request.Request, so see its
            documentation for implications.
        headers: A dictionary of headers to send to the server.
        timeout: A timeout in seconds to be used for blocking operations.

    Returns:
        The raw http.client.HTTPResponse object.

    """
    assert path[0] == "/"

    if headers is None:
        headers = {}

    if params is None:
        params = {}

    if method == "POST" and data is None:
        data = b""

    if isinstance(data, dict):
        data = urllib.parse.urlencode(data).encode()

    full_url = "{}://{}{}{}".format(
        "https" if settings.MANAGER_SSL_CONTEXT is not None else "http",
        settings.MANAGER_HOST,
        path,
        "?" + urllib.parse.urlencode(params) if params else "",
    )

    request = urllib.request.Request(full_url, method=method, data=data, headers=headers)
    try:
        response = urllib.request.urlopen(
            request,
            timeout=timeout,
            context=settings.MANAGER_SSL_CONTEXT,
        )
    except (urllib.error.URLError, socket.timeout, OSError) as ex:
        raise ManagerRequestError(str(ex)) from ex
    # Allow urllib.error.HTTPError to propagate

    return cast(http.client.HTTPResponse, response)
