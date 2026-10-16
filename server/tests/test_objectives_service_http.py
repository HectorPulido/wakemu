"""The standalone evaluator API requires its private bearer token."""
import http.server
import importlib.util
import json
from pathlib import Path
import threading
import urllib.error
import urllib.request
import unittest
from unittest.mock import MagicMock, patch

from wakfu_server.objectives import repository

SERVICE_PATH = Path(__file__).resolve().parents[1] / "objectives-service" / "service.py"
SERVICE_SPEC = importlib.util.spec_from_file_location(
    "objectives_service_under_test", SERVICE_PATH
)
service = importlib.util.module_from_spec(SERVICE_SPEC)
SERVICE_SPEC.loader.exec_module(service)


class ObjectivesServiceHttpTests(unittest.TestCase):
    def setUp(self):
        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), service.Handler)
        self.server.token = "objectives-internal-test-token"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.base = f"http://127.0.0.1:{self.server.server_port}"

    def request(self, method, path, *, token=None, body=None):
        headers = {}
        data = None
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        if body is not None:
            headers["Content-Type"] = "application/json"
            data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.base + path, data=data, headers=headers, method=method
        )
        try:
            response = urllib.request.urlopen(req, timeout=3)
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())
        with response:
            return response.code, json.loads(response.read())

    def test_all_routes_reject_missing_or_nonmatching_bearer_before_database_access(
        self,
    ):
        with patch.object(
            service,
            "connect",
            side_effect=AssertionError("unauthorized request reached DB"),
        ):
            for method, path, body in (
                ("GET", "/health", None),
                ("GET", "/v1/definitions", None),
                ("GET", "/v1/progress?character_id=1", None),
                (
                    "PUT",
                    "/v1/definitions/test",
                    {"definition": {}, "expected_revision": 0},
                ),
            ):
                for token in (None, "objectives-internal-test-token-suffix"):
                    with self.subTest(method=method, path=path, token=token):
                        self.assertEqual(
                            self.request(method, path, token=token, body=body),
                            (401, {"error": "Unauthorized"}),
                        )

    def test_authenticated_definition_read_uses_repository_and_json_response(self):
        with patch.object(service, "connect") as connect, patch.object(
            repository,
            "list_definitions",
            return_value=[{"key": "fixture", "revision": 1}],
        ) as list_definitions:
            db = connect.return_value.__enter__.return_value
            status, payload = self.request(
                "GET", "/v1/definitions", token="objectives-internal-test-token"
            )
        self.assertEqual(status, 200)
        self.assertEqual(payload, {"items": [{"key": "fixture", "revision": 1}]})
        list_definitions.assert_called_once_with(db)

    def test_authenticated_quarantine_retry_resets_attempts_and_records_operator(self):
        connection = MagicMock()
        connection.__enter__.return_value = connection
        connection.execute.return_value.fetchone.return_value = {
            "id": 42,
            "character_id": 7,
            "attempts": 5,
        }
        with patch.object(service, "connect", return_value=connection):
            status, payload = self.request(
                "POST",
                "/v1/events/42/retry",
                token="objectives-internal-test-token",
                body={"operator": "reviewer"},
            )
        self.assertEqual((status, payload), (200, {"id": 42, "status": "pending"}))
        statements = [call.args[0] for call in connection.execute.call_args_list]
        self.assertTrue(any("objectives_event_retries" in sql for sql in statements))
        self.assertTrue(any("SET attempts=0,error=NULL" in sql for sql in statements))
        self.assertTrue(
            any("pg_notify('wakemu_objectives_events'" in sql for sql in statements)
        )
        connection.commit.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
