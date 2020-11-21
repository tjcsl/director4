import unittest

from ..app import app


class RouterTest(unittest.TestCase):
    def setUp(self) -> None:
        app.testing = True
        self.client = app.test_client()

    def test_ping(self) -> None:
        request = self.client.get("/ping")
        self.assertIn(b"Pong", request.data)
