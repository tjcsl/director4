import ssl
from typing import Optional

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
