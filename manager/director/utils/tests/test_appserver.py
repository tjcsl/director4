from websockets.legacy.client import Connect as WebSocketConnect

from ...test.director_test import DirectorTestCase
from ..appserver import (
    AppserverProtocolError,
    appserver_open_http_request,
    appserver_open_websocket,
    get_appserver_addr,
    iter_pingable_appservers,
    iter_random_pingable_appservers,
    ping_appserver,
)


class UtilsAppserverTestCase(DirectorTestCase):
    def test_get_appserver_addr(self):
        self.assertEqual("director-appserver1:8000", get_appserver_addr("director-appserver1:8000"))

        with self.settings(
            DIRECTOR_NUM_APPSERVERS=1,
            DIRECTOR_APPSERVER_HOSTS=["director-appserver1:8000"],
            DIRECTOR_APPSERVER_WS_HOSTS=["director-appserverws1:8000"],
        ):
            self.assertEqual(
                "director-appserver1:8000",
                get_appserver_addr(-1, allow_random=True, websocket=False),
            )
            self.assertEqual("director-appserver1:8000", get_appserver_addr(0, websocket=False))
            self.assertEqual("director-appserverws1:8000", get_appserver_addr(0, websocket=True))

            with self.assertRaises(ValueError):
                self.assertEqual(
                    "director-appserver1:8000",
                    get_appserver_addr(-1, allow_random=False, websocket=False),
                )

    # Figure out some better way to test these
    def test_appserver_open_http_request(self):
        with self.assertRaises(AppserverProtocolError):
            appserver_open_http_request("director-app1test:8000", path="/test", timeout=1)

    def test_ping_appserver(self):
        self.assertFalse(ping_appserver("director-app1test:8000", timeout=1))

    def test_iter_pingable_appservers(self):
        with self.settings(
            DIRECTOR_NUM_APPSERVERS=2,
            DIRECTOR_APPSERVER_HOSTS=["director-balancertest1:8000", "director-balancertest2:8000"],
        ):
            for result in iter_pingable_appservers(timeout=1):
                self.assertFalse(result)

    def test_iter_random_pingable_appservers(self):
        with self.settings(
            DIRECTOR_NUM_APPSERVERS=2,
            DIRECTOR_APPSERVER_HOSTS=["director-balancertest1:8000", "director-balancertest2:8000"],
        ):
            for result in iter_random_pingable_appservers(timeout=1):
                self.assertFalse(result)

    def test_appserver_open_websocket(self):
        self.assertEqual(
            WebSocketConnect,
            type(appserver_open_websocket("director-apptest1", "/test", ping_timeout=1)),
        )
