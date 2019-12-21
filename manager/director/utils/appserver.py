# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import http.client
import json
import random
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple, Union

from django.conf import settings


def create_appserver_ssl_context() -> Optional[ssl.SSLContext]:
    if settings.DIRECTOR_APPSERVER_SSL is None:
        return None

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    context.load_verify_locations(cafile=settings.DIRECTOR_APPSERVER_SSL["cafile"])

    client_certinfo = settings.DIRECTOR_APPSERVER_SSL.get("client_cert", None)
    if client_certinfo is not None:
        context.load_cert_chain(
            certfile=client_certinfo["certfile"],
            keyfile=client_certinfo.get("keyfile"),
            password=lambda: client_certinfo["password"],
        )

    return context


appserver_ssl_context = create_appserver_ssl_context()


class AppserverRequestError(Exception):
    pass


class AppserverProtocolError(AppserverRequestError):
    pass


class AppserverConnectionError(AppserverRequestError):
    pass


class AppserverTimeoutError(AppserverRequestError):
    pass


class AppserverHTTPResponse:  # pylint: disable=too-many-instance-attributes
    ENCODING_REGEX = re.compile(
        r"""^.*;\s*charset=(?P<charset>([^;'"\s]|\S;)+|'([^']|\\')+'|"([^"]|\\")+")\s*(;.*)?$"""
    )

    def __init__(
        self, appserver: str, path: str, full_url: str, response: http.client.HTTPResponse
    ):
        self.appserver = appserver
        self.path = path
        self.full_url = full_url
        self.response = response

        try:
            self.appserver_index = settings.DIRECTOR_APPSERVER_HOSTS.index(appserver)
        except ValueError:
            self.appserver_index = -1

        self._content: Optional[bytes] = None
        self._text: Optional[str] = None
        self._encoding: Optional[str] = None

    @property
    def encoding(self) -> Optional[str]:
        if self._encoding is None:
            value = self.response.getheader("content-type")
            if value is None:
                self._encoding = None
            else:
                match = self.ENCODING_REGEX.search(value)
                if match is not None:
                    raw_charset = match.group("charset")
                    if raw_charset[0] == raw_charset[-1] and raw_charset[0] in "'\"":
                        raw_charset = raw_charset[1:-1].replace(
                            "\\" + raw_charset[0], raw_charset[0]
                        )

                    self._encoding = raw_charset

        return self._encoding

    @property
    def content(self) -> bytes:
        if self._content is None:
            self._content = self.response.read()

        return self._content

    @property
    def text(self) -> str:
        if self._text is None:
            self._text = (
                self.content.decode(self.encoding)
                if self.encoding is not None
                else self.content.decode()
            )

        return self._text

    def json(self) -> Any:
        return json.loads(self.text)


def get_appserver_addr(appserver: Union[int, str], *, allow_random: bool = True) -> str:
    """Given the index or address for a given appserver, normalizes it to a
    "host:port" address combo.

    Args:
        appserver: Either 1) the "host:port" combo for the appserver to connect
            to (as a string), 2) the index (0-based) of the appserver in
            ``settings.DIRECTOR_APPSERVER_HOSTS`` to connect to, or 3) a
            negative number to indicate that a random appserver should be
            chosen (if allow_random is ``True``).
        allow_random:
            Whether to allow selecting a random appserver.

    Returns:
        The "host:port" combo for the appserver to connect to

    """
    if isinstance(appserver, int):
        assert settings.DIRECTOR_NUM_APPSERVERS

        if appserver < 0:
            if allow_random:
                appserver = random.randint(0, settings.DIRECTOR_NUM_APPSERVERS - 1)
            else:
                raise ValueError("appserver index cannot be negative if allow_random is False")

        appserver = settings.DIRECTOR_APPSERVER_HOSTS[appserver]

    return appserver


def appserver_open_http_request(
    appserver: Union[int, str],
    path: str,
    *,
    method: str = "GET",
    params: Union[Dict[str, str], Sequence[Tuple[str, str]], None] = None,
    data: Optional[bytes] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: Union[int, float] = settings.DIRECTOR_APPSERVER_DEFAULT_TIMEOUT,
) -> AppserverHTTPResponse:
    """Opens an HTTP request to the given appserver and returns an
    AppserverHTTPResponse wrapping the response.

    Args:
        appserver: Either 1) the "host:port" combo for the appserver to connect
            to (as a string), 2) the index (0-based) of the appserver in
            ``settings.DIRECTOR_APPSERVER_HOSTS`` to connect to, or 3) a
            negative number to indicate that a random appserver should be
            chosen.
        path: The path to request from the server. Should have a leading slash.
        method: The HTTP method to use (like GET or POST).
        data: An object specifying additional data to send to the server.
            This is passed directly to urllib.request.Request, so see its
            documentation for implications.
        headers: A dictionary of headers to send to the server.
        timeout: A timeout in seconds to be used for blocking operations.

    Returns:
        An AppserverHTTPResponse object representing the response from the
        appserver.

    """
    assert path[0] == "/"

    appserver = get_appserver_addr(appserver, allow_random=True)

    if headers is None:
        headers = {}

    if params is None:
        params = {}

    if method == "POST" and data is None:
        data = b""

    full_url = "{}://{}{}{}".format(
        "https" if settings.DIRECTOR_APPSERVER_SSL else "http",
        appserver,
        path,
        "?" + urllib.parse.urlencode(params) if params else "",
    )

    request = urllib.request.Request(full_url, method=method, data=data, headers=headers)
    try:
        response = urllib.request.urlopen(request, timeout=timeout, context=appserver_ssl_context)
    except urllib.error.URLError as ex:
        if isinstance(ex.reason, ConnectionError):
            raise AppserverConnectionError(str(ex)) from ex

        if isinstance(ex.reason, socket.timeout):
            raise AppserverTimeoutError(str(ex)) from ex

        raise AppserverProtocolError(str(ex)) from ex
    except socket.timeout as ex:
        raise AppserverTimeoutError(str(ex)) from ex
    except ConnectionError as ex:
        raise AppserverConnectionError(str(ex)) from ex
    except OSError as ex:
        raise AppserverRequestError(str(ex)) from ex

    return AppserverHTTPResponse(
        appserver=appserver, path=path, full_url=full_url, response=response
    )


def ping_appserver(appserver: Union[int, str], *, timeout: Union[int, float] = 2) -> bool:
    """Attempts to ping the given appserver by issuing a request to /ping.
    Returns whether the attempt was successful.

    Args:
        appserver: Either the "host:port" combo for the appserver to connect
            to (as a string) or the index (0-based) of the appserver in
            ``settings.DIRECTOR_APPSERVER_HOSTS`` to connect to.
        timeout: The timeout to use when connecting to the given appserver.

    Returns:
        Whether the attempt to contact the given appserver was successful.

    """
    message = "Pong {}".format(appserver)

    try:
        response = appserver_open_http_request(
            get_appserver_addr(appserver, allow_random=False),
            "/ping?" + urllib.parse.urlencode({"message": message}),
            method="GET",
            timeout=timeout,
        )
    except AppserverRequestError:
        return False
    else:
        return response.content == message.encode() + b"\n"


def iter_pingable_appservers(*, timeout: Union[int, float] = 2) -> Iterator[int]:
    """Attempts to ping every appserver listed in ``settings.DIRECTOR_APPSERVER_HOSTS``
    and returns a iterator yielding the indices of each appserver that was successfully
    pinged.

    Appservers are only pinged as necessary to yield the next value. If you want to ping
    all of them at once, create a list or a tuple from the items yielded by this iterator.

    Args:
        timeout: The timeout to use when connecting to the appservers.

    Returns:
        A list of the indices of each appserver that was successfully pinged.

    """
    for i in range(settings.DIRECTOR_NUM_APPSERVERS):
        if ping_appserver(i, timeout=timeout):
            yield i
