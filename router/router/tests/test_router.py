import unittest
from unittest.mock import mock_open, patch

from ..app import app


class RouterTest(unittest.TestCase):
    def setUp(self) -> None:
        app.testing = True
        self.client = app.test_client()

    def test_ping(self) -> None:
        request = self.client.get("/ping")
        self.assertEqual(b"Pong", request.data)

    def test_update_nginx_page(self) -> None:
        request = self.client.post("/sites/1234/update-nginx")
        self.assertEqual(400, request.status_code)

        request = self.client.post(
            "/sites/1234/update-nginx", data={"data": '{"name": "hello", "custom_domains": {}}'}
        )
        self.assertEqual(500, request.status_code)

        mock_open_obj = mock_open()
        with patch("router.nginx.open", mock_open_obj):
            with patch("router.nginx.settings.NGINX_RELOAD_COMMAND", "echo"):
                request = self.client.post(
                    "/sites/1234/update-nginx",
                    data={"data": '{"name": "hello", "custom_domains": {}}'},
                )

        self.assertEqual(200, request.status_code)
        self.assertEqual(b"Success", request.data)

        mock_open_obj = mock_open()
        with patch("router.nginx.open", mock_open_obj):
            with patch("router.nginx.settings.NGINX_RELOAD_COMMAND", "echo"):
                request = self.client.post(
                    "/sites/1234/update-nginx",
                    data={"data": '{"name": "hello", "custom_domains": ["tjhsst.edu"]}'},
                )

        self.assertEqual(200, request.status_code)
        self.assertEqual(b"Success", request.data)

    def test_remove_nginx_page(self) -> None:
        request = self.client.post("/sites/1234/remove-nginx")
        self.assertEqual(200, request.status_code)

        with patch("router.nginx.os.path.exists", return_value=True):
            request = self.client.post("/sites/1234/remove-nginx")

        self.assertEqual(500, request.status_code)

    def test_setup_certbot_page(self) -> None:
        request = self.client.post("/sites/1234/certbot-setup")
        self.assertEqual(400, request.status_code)
        self.assertEqual(b"Error", request.data)

        with patch("router.certbot.subprocess.run", return_value=True) as mock_obj:
            request = self.client.post(
                "/sites/1234/certbot-setup",
                data={"data": '{"name": "hello", "custom_domains": []}'},
            )

            self.assertEqual(200, request.status_code)
            self.assertEqual(b"Success", request.data)

        mock_obj.assert_called_once()

    def test_remove_old_certbot_domains_page(self) -> None:
        request = self.client.post("/sites/certbot-remove-old-domains")
        self.assertEqual(400, request.status_code)
        self.assertEqual(b"Error", request.data)

        with patch("router.certbot.subprocess.run", return_value=True) as mock_obj:
            request = self.client.post(
                "/sites/certbot-remove-old-domains",
                data={"domains": '["tjhsst.edu", "tjhsst.fcps.edu", "sysadmins.tjhsst.edu"]'},
            )

            self.assertEqual(200, request.status_code)
            self.assertEqual(b"Success", request.data)

        mock_obj.assert_called_once()
