import json
import os
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

from health_server import start_health_server


class HealthServerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_port = os.environ.get("PORT")
        os.environ["PORT"] = "0"
        self.server = start_health_server()
        if self.server is None:
            self.fail("Health server did not start with PORT set")
        self.base_url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        if self.previous_port is None:
            os.environ.pop("PORT", None)
        else:
            os.environ["PORT"] = self.previous_port

    def test_healthz_returns_200_json(self) -> None:
        with urlopen(f"{self.base_url}/healthz", timeout=2) as response:
            self.assertEqual(response.status, 200)
            self.assertEqual(response.headers.get_content_type(), "application/json")
            self.assertEqual(json.load(response), {"status": "ok"})

    def test_unknown_path_returns_404_json(self) -> None:
        with self.assertRaises(HTTPError) as context:
            urlopen(f"{self.base_url}/missing", timeout=2)
        with context.exception as response:
            self.assertEqual(response.code, 404)
            self.assertEqual(response.headers.get_content_type(), "application/json")
            self.assertEqual(json.load(response), {"error": "not found"})
