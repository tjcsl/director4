# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
from typing import Any, Dict, Optional, cast

import websockets
from asgiref.sync import async_to_sync
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncWebsocketConsumer, JsonWebsocketConsumer
from channels.layers import get_channel_layer

from django.conf import settings

from ...utils.appserver import appserver_open_websocket
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
            self.site = Site.objects.filter_for_user(self.scope["user"]).get(id=site_id)
        except Site.DoesNotExist:
            self.close()
            return

        async_to_sync(self.channel_layer.group_add)(
            self.site.channels_group_name, self.channel_name,
        )

        self.connected = True
        self.accept()

        self.send_site_info()

    def disconnect(self, code: int) -> None:
        if self.site is not None:
            async_to_sync(self.channel_layer.group_discard)(
                self.site.channels_group_name, self.channel_name,
            )

        self.site = None
        self.connected = False

    def receive_json(self, content: Any, **kwargs: Any) -> None:
        if self.connected:
            pass

    def operation_updated(self, event: Dict[str, Any]) -> None:
        self.send_site_info()

    def send_site_info(self) -> None:
        if self.connected:
            assert self.site is not None

            site_info = {
                "name": self.site.name,
                "description": self.site.description,
                "type": self.site.type,
            }

            # This should be a format that Javascript can parse natively
            datetime_format = "%Y-%m-%d %H:%M:%S %Z"

            if self.site.has_operation:
                site_info["operation"] = {
                    "type": self.site.operation.type,
                    "created_time": (
                        self.site.operation.created_time.strftime(datetime_format)
                        if self.site.operation.created_time is not None
                        else None
                    ),
                    "started_time": (
                        self.site.operation.started_time.strftime(datetime_format)
                        if self.site.operation.started_time is not None
                        else None
                    ),
                    "actions": [
                        {
                            "slug": action.slug,
                            "name": action.name,
                            "started_time": (
                                action.started_time.strftime(datetime_format)
                                if action.started_time is not None
                                else None
                            ),
                            "result": action.result,
                            # The following fields are intentionally omitted:
                            # before_state, after_state, equivalent_command, message
                            # Do not add them in.
                        }
                        for action in self.site.operation.list_actions_in_order()
                    ],
                }
            else:
                site_info["operation"] = None

            self.send_json({"site_info": site_info})


class SiteTerminalConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.site: Optional[Site] = None
        self.connected = False

        self.terminal_websock: Optional[websockets.client.WebSocketClientProtocol] = None

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

        if self.connected:
            loop = asyncio.get_event_loop()
            loop.create_task(self.mainloop())

    @database_sync_to_async
    def get_site_for_user(self, user, **kwargs: Any) -> Site:  # pylint: disable=no-self-use
        return cast(Site, Site.objects.filter_for_user(user).get(**kwargs))

    async def open_terminal_connection(self) -> None:
        assert self.site is not None

        appserver_num = hash(str(self.site.id) + self.site.name) % settings.DIRECTOR_NUM_APPSERVERS

        orig_appserver_num = appserver_num

        while True:
            try:
                self.terminal_websock = await asyncio.wait_for(
                    appserver_open_websocket(
                        appserver_num, "/ws/sites/{}/terminal".format(self.site.id)
                    ),
                    timeout=1,
                )

                # We successfully connected; keep going
                break
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake):
                # Connection failure; try the next appserver
                appserver_num = (appserver_num + 1) % settings.DIRECTOR_NUM_APPSERVERS

                if appserver_num == orig_appserver_num:
                    # We've come full circle; none are reachable
                    await self.close()
                    return

        try:
            assert self.terminal_websock is not None

            await self.terminal_websock.send(
                json.dumps(await database_sync_to_async(self.site.serialize_for_appserver)())
            )
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException):
            self.connected = False
            await self.close()

    async def mainloop(self) -> None:
        assert self.terminal_websock is not None

        while True:
            try:
                msg = await self.terminal_websock.recv()
            except websockets.exceptions.ConnectionClosed:
                await self.close()
                break

            if isinstance(msg, bytes):
                await self.send(bytes_data=msg)
            elif isinstance(msg, str):
                await self.send(text_data=msg)

    async def disconnect(self, code: int) -> None:  # pylint: disable=unused-argument
        self.site = None
        self.connected = False

        if self.terminal_websock is not None:
            await self.terminal_websock.close()
            self.terminal_websock = None

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        if self.connected and self.terminal_websock is not None:
            if bytes_data is not None:
                await self.terminal_websock.send(bytes_data)
            elif text_data is not None:
                await self.terminal_websock.send(text_data)
