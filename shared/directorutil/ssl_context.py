# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import ssl
from typing import Any, Dict, Optional


def create_internal_client_ssl_context(
    ssl_settings: Optional[Dict[str, Any]],
) -> Optional[ssl.SSLContext]:
    """Create an SSL context based on the given SSL settings for connecting to internal
    Director servers (i.e. manager -> orchestrator, shell server -> manager).

    WARNING: Do not use this for anything other than internal connections!

    If ssl_settings is None, this function returns None. Otherwise,
    ssl_settings must be a dictionary in the following format:
    {
        "cafile": "<path to CA file used to verify server certificates>",
        "client_cert": {
            "certfile": "<path to client certificate file>",  # Required
            "keyfile": "<path to client private key file>",  # Taken from certfile if not passed
            "password": "<private key password>",  # Required if private key is encrypted
        },
    }

    (The "client_cert" parameter is optional.)

    Some additional parameters are set on the SSL context:
     - It is set up for use authenticating servers (creating client-side sockets)
     - A certificate is required and validated upon reception.
     - HOSTNAME CHECKING IS DISABLED. As a result, "cafile" MUST point to a trusted CA!
       It is recommended to use a self-signed certificate on the remote server and point
       "cafile" to this certificate.

    """

    if ssl_settings is None:
        return None

    context = ssl.create_default_context(
        purpose=ssl.Purpose.SERVER_AUTH, cafile=ssl_settings["cafile"],
    )
    context.verify_mode = ssl.CERT_REQUIRED
    context.check_hostname = False

    if hasattr(ssl, "TLSVersion"):  # Added in Python 3.7
        context.minimum_version = ssl.TLSVersion.TLSv1_2  # type: ignore # pylint: disable=no-member

    client_certinfo = ssl_settings.get("client_cert", None)
    if client_certinfo is not None:
        context.load_cert_chain(
            certfile=client_certinfo["certfile"],
            keyfile=client_certinfo.get("keyfile"),
            password=lambda: client_certinfo["password"],  # type: ignore
        )

    return context
