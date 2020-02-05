# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
from typing import Any, Optional

from django.conf import settings

from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer, JsonWebsocketConsumer

from ...utils.appserver import appserver_open_websocket, ping_appserver
from .models import Site

import websockets


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


class SiteTerminalConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.site: Optional[Site] = None
        self.connected = False

        self.terminal_websock: Optional[websockets.client.Connect] = None

    async def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        site_id = int(self.scope["url_route"]["kwargs"]["site_id"])
        try:
            self.site = await self.get_site_for_user(self.scope["user"], id=site_id)
        except Site.DoesNotExist:
            await self.close()
            return

        self.connected = True
        await self.accept()

        await self.open_terminal_connection()

        loop = asyncio.get_event_loop()
        loop.create_task(self.mainloop())

    @database_sync_to_async
    def get_site_for_user(self, user: "get_user_model()", **kwargs: Any) -> Site:
        return Site.objects.filter_for_user(user).get(**kwargs)

    async def open_terminal_connection(self) -> None:
        appserver_num = hash(str(self.site.id) + self.site.name) % settings.DIRECTOR_NUM_APPSERVERS

        orig_appserver_num = appserver_num

        # If we can't ping this one, go to the next one
        while not ping_appserver(appserver_num, timeout=1):
            appserver_num = (appserver_num + 1) % settings.DIRECTOR_NUM_APPSERVERS

            # We've come full circle; none are reachable
            if appserver_num == orig_appserver_num:
                await self.close()
                return

        try:
            self.terminal_websock = await asyncio.wait_for(
                appserver_open_websocket(
                    appserver_num,
                    "/ws/terminal",
                ),
                timeout=5,
            )

            await self.terminal_websock.send(
                json.dumps(
                    {
                        "site_id": self.site.id,
                        "data": await database_sync_to_async(self.site.serialize_for_appserver)(),
                    }
                ),
            )
        except (OSError, asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
            self.connected = False
            await self.close()

    async def mainloop(self) -> None:
        while True:
            try:
                msg = await self.terminal_websock.recv()
            except websockets.exceptions.ConnectionClosed:
                await self.close()
                break

            await self.send(bytes_data=msg)

    async def disconnect(self, close_code: int) -> None:
        self.site = None
        self.connected = False

        if self.terminal_websock is not None:
            await self.terminal_websock.close()
            self.terminal_websock = None

    async def receive(self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None) -> None:
        if self.connected:
            if bytes_data is not None:
                await self.terminal_websock.send(bytes_data)
            else:
                await self.terminal_websock.send(text_data)
