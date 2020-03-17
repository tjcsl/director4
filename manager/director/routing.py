# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Optional

from channels.auth import AuthMiddlewareStack
from channels.generic.websocket import WebsocketConsumer
from channels.routing import ProtocolTypeRouter, URLRouter

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


application = ProtocolTypeRouter(
    {
        "websocket": AuthMiddlewareStack(
            URLRouter(
                [
                    path("sites/<int:site_id>/", SiteConsumer),
                    path("sites/<int:site_id>/terminal/", SiteTerminalConsumer),
                    path("sites/<int:site_id>/files/monitor/", SiteMonitorConsumer),
                    path("sites/<int:site_id>/logs/", SiteLogsConsumer),
                    path("sites/multi-status/", MultiSiteStatusConsumer),
                    path("<path:path>", WebsocketCloseConsumer),
                ]
            )
        )
    }
)
