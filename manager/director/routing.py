# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Optional

from channels.auth import AuthMiddlewareStack
from channels.generic.websocket import WebsocketConsumer
from channels.routing import ProtocolTypeRouter, URLRouter

from django.urls import path

from director.apps.sites.consumers import SiteConsumer


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
                    path("<path:path>", WebsocketCloseConsumer),
                ]
            )
        )
    }
)
