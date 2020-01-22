# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

from typing import Any, Optional

from channels.generic.websocket import JsonWebsocketConsumer

from .models import Site


class SiteConsumer(JsonWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.site: Optional[Site] = None
        self.connected = False

    def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            self.close()
            return

        site_id = int(self.scope["url_route"]["kwargs"]["site_id"])
        try:
            self.site = Site.objects.get(users=self.scope["user"], id=site_id)
        except Site.DoesNotExist:
            self.close()
            return

        self.connected = True
        self.accept()

        self.send_site_info()

    def disconnect(self, code: int) -> None:
        self.site = None
        self.connected = False

    def receive_json(self, content: Any, **kwargs: Any) -> None:
        if self.connected:
            pass

    def send_site_info(self) -> None:
        if self.connected:
            assert self.site is not None

            self.send_json(
                {
                    "site_info": {
                        "name": self.site.name,
                        "description": self.site.description,
                        "type": self.site.type,
                    },
                }
            )
