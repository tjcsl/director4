# SPDX-License-Identifier: MIT
# (c) 2019 The TJHSST Director 4.0 Development Team & Contributors

import asyncio
import json
import urllib.parse
from typing import Any, Dict, List, Optional, Union, cast

import websockets
from channels.db import database_sync_to_async
from channels.generic.websocket import AsyncJsonWebsocketConsumer, AsyncWebsocketConsumer

from django.conf import settings

from ...utils.appserver import (
    appserver_open_websocket,
    iter_pingable_appservers,
    iter_random_pingable_appservers,
)
from .models import Database, Site


class SiteConsumer(AsyncJsonWebsocketConsumer):
    """A websocket consumer that sends information on the site."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.site: Optional[Site] = None
        self.connected = False

        self.status_websocket: Optional[websockets.client.WebSocketClientProtocol] = None

    async def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        site_id = int(self.scope["url_route"]["kwargs"]["site_id"])
        try:
            self.site = await get_site_for_user(self.scope["user"], id=site_id)
        except Site.DoesNotExist:
            # Site does not exist
            await self.accept()

            # If connected=True and site=None, send_site_info() will send "null".
            # This allows the page to recognize that the site doesn't exist and display the
            # "site deleted" message.
            self.connected = True
            await self.send_site_info()
            self.connected = False

            await self.close()
            return

        # Listen for events on the site
        assert self.site is not None
        await self.channel_layer.group_add(
            self.site.channels_group_name, self.channel_name,
        )

        if self.site.type == "dynamic":
            # For dynamic sites, watch for changes in the site status
            await self.open_status_websocket()

            if self.status_websocket is not None:
                self.connected = True
                await self.accept()

                await self.send_site_info()

                asyncio.get_event_loop().create_task(self.status_websocket_mainloop())
        else:
            self.connected = True
            await self.accept()

            await self.send_site_info()

    async def open_status_websocket(self) -> None:
        assert self.site is not None

        for i in range(settings.DIRECTOR_NUM_APPSERVERS):
            try:
                self.status_websocket = await asyncio.wait_for(
                    appserver_open_websocket(i, "/ws/sites/{}/status".format(self.site.id)),
                    timeout=1,
                )

                # We successfully connected; break
                break
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake):
                pass  # Connection failure; try the next appserver

        if self.status_websocket is None:
            await self.close()
            self.connected = False
            return

    async def status_websocket_mainloop(self) -> None:
        assert self.status_websocket is not None

        # Forward status messages to the client
        while True:
            try:
                msg = await self.status_websocket.recv()
            except websockets.exceptions.ConnectionClosed:
                await self.close()
                self.connected = False
                break

            if isinstance(msg, str):
                await self.send_json({"site_status": json.loads(msg)})

    async def disconnect(self, code: int) -> None:
        # Clean up
        if self.site is not None:
            await self.channel_layer.group_discard(
                self.site.channels_group_name, self.channel_name,
            )

        self.site = None
        self.connected = False

        if self.status_websocket is not None:
            await self.status_websocket.close()

    async def receive_json(self, content: Any, **kwargs: Any) -> None:
        # Ignore messages
        if self.connected:
            pass

    async def site_updated(self, event: Dict[str, Any]) -> None:  # pylint: disable=unused-argument
        await self.send_site_info()

    async def operation_updated(
        self, event: Dict[str, Any]  # pylint: disable=unused-argument
    ) -> None:
        await self.send_site_info()

    @database_sync_to_async
    def dump_site_info(self) -> Union[Dict[str, Any], None, bool]:
        # If this method returns:
        # a dictionary: Everything is OK, this should be sent to the client.
        # None: The site doesn't exist. Send this to the client so it knows.
        # False: The site type has changed. Close the connection. When the client reopens the
        #   connection, we can check the site type again and adapt to handle it.

        if self.site is None:
            return None

        old_type = self.site.type

        try:
            self.site.refresh_from_db()
        except Site.DoesNotExist:
            return None

        if self.site.type != old_type:
            return False

        site_info: Dict[str, Any] = {
            "name": self.site.name,
            "main_url": self.site.main_url,
            "description": self.site.description,
            "purpose": self.site.purpose,
            "purpose_display": self.site.get_purpose_display(),
            "type": self.site.type,
            "type_display": self.site.get_type_display(),
            "users": list(self.site.users.values_list("username", flat=True)),
        }

        if self.site.has_database:
            database = Database.objects.get(site=self.site)

            site_info["database"] = {
                "username": database.username,
                "password": database.password,
                "db_host": database.db_host,
                "db_port": database.db_port,
                "db_type": database.db_type,
                "db_url": database.db_url,
            }
        else:
            site_info["database"] = None

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

        return site_info

    async def send_site_info(self) -> None:
        if self.connected:
            data = await self.dump_site_info()

            if data is False:
                await self.close()
            else:
                await self.send_json({"site_info": data})


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
            self.site = await get_site_for_user(self.scope["user"], id=site_id)
        except Site.DoesNotExist:
            await self.close()
            return

        self.connected = True
        await self.accept()

        await self.open_terminal_connection()

        if self.connected:
            loop = asyncio.get_event_loop()
            loop.create_task(self.mainloop())

    async def open_terminal_connection(self) -> None:
        assert self.site is not None

        # This is a little tricky. We have two goals here:
        # 1) Spread the load across the appservers, since opening a terminal container can be
        #    resource-intensive.
        # 2) Try to open all terminals for a given site on the same appserver so that we don't end
        #    up opening duplicate terminals, which is wasteful.
        # Here's how we satisfy both: We take a hash of the site ID + site name, modulus the number
        # of appservers, and try to connect to that numbered appserver. If the conection fails, we
        # move on to the next appserver (wrapping around, so if there are 3 appservers and we start
        # with appserver 1, it will try 2 and then wrap around to 0).

        appserver_num = hash(str(self.site.id) + self.site.name) % settings.DIRECTOR_NUM_APPSERVERS

        orig_appserver_num = appserver_num

        while True:
            try:
                # Try to open a connection.
                terminal_websock = await asyncio.wait_for(
                    appserver_open_websocket(
                        appserver_num, "/ws/sites/{}/terminal".format(self.site.id)
                    ),
                    timeout=1,
                )

                # We successfully connected; break
                break
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake):
                # Connection failure; try the next appserver
                appserver_num = (appserver_num + 1) % settings.DIRECTOR_NUM_APPSERVERS

                if appserver_num == orig_appserver_num:
                    # We've come full circle; none are reachable
                    self.connected = False
                    await self.close()
                    return

        try:
            # Send the site information so the appserver knows how to set everything up.
            await terminal_websock.send(
                json.dumps(await database_sync_to_async(self.site.serialize_for_appserver)())
            )

            # We wait until here to assign it to self.terminal_websock. Otherwise the client
            # could send JSON data really quickly and perhaps get that sent to the appserver
            # instead of our data above.
            self.terminal_websock = terminal_websock
        except (OSError, asyncio.TimeoutError, websockets.exceptions.WebSocketException):
            self.connected = False
            await self.close()

    async def mainloop(self) -> None:
        assert self.terminal_websock is not None

        # Just forward messages through
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
        # Clean up

        self.site = None
        self.connected = False

        if self.terminal_websock is not None:
            await self.terminal_websock.close()
            self.terminal_websock = None

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        # Just forward messages through
        if self.connected and self.terminal_websock is not None:
            try:
                if bytes_data is not None:
                    await self.terminal_websock.send(bytes_data)
                elif text_data is not None:
                    await self.terminal_websock.send(text_data)
            except websockets.exceptions.ConnectionClosed:
                await self.close()


class SiteMonitorConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.site: Optional[Site] = None
        self.connected = False

        self.monitor_websocks: List[websockets.client.WebSocketClientProtocol] = []

    async def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        site_id = int(self.scope["url_route"]["kwargs"]["site_id"])
        try:
            self.site = await get_site_for_user(self.scope["user"], id=site_id)
        except Site.DoesNotExist:
            await self.close()
            return

        self.connected = True
        await self.accept()

        await self.open_monitor_connections()

        if self.monitor_websocks:
            loop = asyncio.get_event_loop()
            for monitor_websock in self.monitor_websocks:
                loop.create_task(self.monitor_mainloop(monitor_websock))
        else:
            self.connected = False
            await self.close()

    async def open_monitor_connections(self) -> None:
        assert self.site is not None

        for appserver_num in iter_pingable_appservers():
            try:
                monitor_websock = await asyncio.wait_for(
                    appserver_open_websocket(
                        appserver_num, "/ws/sites/{}/files/monitor".format(self.site.id)
                    ),
                    timeout=1,
                )
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake):
                pass
            else:
                self.monitor_websocks.append(monitor_websock)

    async def monitor_mainloop(
        self, monitor_websock: websockets.client.WebSocketClientProtocol,
    ) -> None:
        while True:
            try:
                msg = await monitor_websock.recv()
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

        while self.monitor_websocks:
            await self.monitor_websocks.pop().close()

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        if self.connected:
            data = bytes_data if bytes_data is not None else text_data

            if data is None:
                return

            try:
                for monitor_websock in self.monitor_websocks:
                    await monitor_websock.send(data)
            except websockets.exceptions.ConnectionClosed:
                await self.close()


class SiteLogsConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)

        self.site: Optional[Site] = None

        self.logs_websock: Optional[websockets.client.WebSocketClientProtocol] = None

    async def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        site_id = int(self.scope["url_route"]["kwargs"]["site_id"])
        try:
            self.site = await get_site_for_user(self.scope["user"], id=site_id)
        except Site.DoesNotExist:
            await self.close()
            return

        await self.open_log_connection()

        if self.logs_websock is None:
            await self.close()
        else:
            await self.accept()

            asyncio.get_event_loop().create_task(self.mainloop())

    async def open_log_connection(self):
        assert self.site is not None

        for i in range(settings.DIRECTOR_NUM_APPSERVERS):
            try:
                self.logs_websock = await asyncio.wait_for(
                    appserver_open_websocket(i, "/ws/sites/{}/logs".format(self.site.id)),
                    timeout=1,
                )

                # We successfully connected; break
                break
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake):
                pass  # Connection failure; try the next appserver

    async def mainloop(self) -> None:
        assert self.logs_websock is not None

        while True:
            try:
                msg = await self.logs_websock.recv()
            except websockets.exceptions.ConnectionClosed:
                await self.close()
                break

            if isinstance(msg, bytes):
                await self.send(bytes_data=msg)
            elif isinstance(msg, str):
                await self.send(text_data=msg)

    async def disconnect(self, code: int) -> None:  # pylint: disable=unused-argument
        self.site = None

        if self.logs_websock is not None:
            await self.logs_websock.close()
            self.logs_websock = None

    async def receive(
        self, text_data: Optional[str] = None, bytes_data: Optional[bytes] = None
    ) -> None:
        data = bytes_data if bytes_data is not None else text_data

        if data is None:
            return

        if self.logs_websock is not None:
            try:
                await self.logs_websock.send(data)
            except websockets.exceptions.ConnectionClosed:
                await self.close()


class MultiSiteStatusConsumer(AsyncWebsocketConsumer):
    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.connected = False

        self.site_ids: List[int] = []

        self.monitor_websock: Optional[websockets.client.WebSocketClientProtocol] = None

    async def connect(self) -> None:
        if not self.scope["user"].is_authenticated:
            await self.close()
            return

        params = urllib.parse.parse_qs(self.scope["query_string"].decode())

        try:
            self.site_ids = list(map(int, params.get("site_ids", [""])[0].split(",")))
        except ValueError:
            await self.close()
            return

        for site_id in self.site_ids:
            try:
                await get_site_for_user(self.scope["user"], id=site_id)
            except Site.DoesNotExist:
                await self.close()
                return

        self.connected = True
        await self.accept()

        await self.open_monitor_connection()

        if self.monitor_websock is not None:
            asyncio.get_event_loop().create_task(self.monitor_mainloop(self.monitor_websock))
        else:
            self.connected = False
            await self.close()

    async def open_monitor_connection(self) -> None:
        for appserver_num in iter_random_pingable_appservers():
            try:
                monitor_websock = await asyncio.wait_for(
                    appserver_open_websocket(appserver_num, "/ws/sites/multi-status/"), timeout=1,
                )
            except (OSError, asyncio.TimeoutError, websockets.exceptions.InvalidHandshake):
                pass
            else:
                await monitor_websock.send(json.dumps(self.site_ids))
                # Don't assign to self.monitor_websock until we've sent the data, to prevent the
                # client from sending JSON data before we do and getting theirs sent to the
                # appserver first.
                self.monitor_websock = monitor_websock

                return

    async def monitor_mainloop(
        self, monitor_websock: websockets.client.WebSocketClientProtocol,
    ) -> None:
        while True:
            try:
                msg = await monitor_websock.recv()
            except websockets.exceptions.ConnectionClosed:
                await self.close()
                break

            if isinstance(msg, bytes):
                await self.send(bytes_data=msg)
            elif isinstance(msg, str):
                await self.send(text_data=msg)

    async def disconnect(self, code: int) -> None:  # pylint: disable=unused-argument
        self.site_ids.clear()
        self.connected = False

        if self.monitor_websock is not None:
            await self.monitor_websock.close()


@database_sync_to_async
def get_site_for_user(user, **kwargs: Any) -> Site:
    return cast(Site, Site.objects.filter_for_user(user).get(**kwargs))
