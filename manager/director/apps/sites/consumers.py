# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any

from channels.generic.websocket import JsonWebsocketConsumer


class SiteConsumer(JsonWebsocketConsumer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.site = None
        self.connected = False

    def connect(self) -> None:
        site_id = self.scope["url_route"]["kwargs"][  # pylint: disable=unused-variable # noqa
            "site_id"
        ]

        self.connected = True
        self.accept()

        self.send_site_info()

    def disconnect(self, code: int) -> None:
        self.site = None
        self.connected = False

    def receive_json(self, content: Any, **kwargs) -> None:
        if self.connected:
            pass

    def send_site_info(self) -> None:
        if self.connected:
            self.send_json(
                {"site_info": {}, }
            )
