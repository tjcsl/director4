# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Optional

from channels.auth import AuthMiddlewareStack
from channels.generic.websocket import WebsocketConsumer
from channels.routing import ProtocolTypeRouter, URLRouter

from django.core.asgi import get_asgi_application
from django.urls import path

from director.apps.sites.consumers import (
    MultiSiteStatusConsumer,
    SiteConsumer,
    SiteLogsConsumer,
    SiteMonitorConsumer,
    SiteTerminalConsumer,
)


class WebsocketCloseConsumer(WebsocketConsumer):
    def connect(self) -> None:
        self.accept()
        self.close()

    def receive(self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None) -> None:
        pass

    def disconnect(self, code: int) -> None:
        pass


django_asgi_app = get_asgi_application()

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AuthMiddlewareStack(
            URLRouter(
                [
                    path("sites/<int:site_id>/", SiteConsumer.as_asgi()),
                    path("sites/<int:site_id>/terminal/", SiteTerminalConsumer.as_asgi()),
                    path("sites/<int:site_id>/files/monitor/", SiteMonitorConsumer.as_asgi()),
                    path("sites/<int:site_id>/logs/", SiteLogsConsumer.as_asgi()),
                    path("sites/multi-status/", MultiSiteStatusConsumer.as_asgi()),
                    path("<path:path>", WebsocketCloseConsumer.as_asgi()),
                ]
            )
        ),
    }
)
