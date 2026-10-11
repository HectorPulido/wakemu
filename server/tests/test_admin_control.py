"""Lifecycle broker contracts with fake Docker; these tests never invoke Docker."""
import json
from pathlib import Path
import threading
import tempfile
import unittest
import urllib.error
import urllib.request

from wakfu_server.admin_control import DockerControl, OperationManager, make_server


class AdminControlTests(unittest.TestCase):
    def test_operation_requests_are_idempotent_and_recover_after_broker_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manager = OperationManager(None, root, start_worker=False)
            first = manager.submit({"service": "world", "request_id": "request_123456"})
            duplicate = manager.submit(
                {"service": "world", "request_id": "request_123456"}
            )
            self.assertEqual(first["handle"], duplicate["handle"])
            with self.assertRaises(ValueError):
                manager.submit({"service": "shop", "request_id": "request_123456"})

            interrupted = dict(
                handle="a" * 32,
                request_id="request_interrupted",
                request_hash="b" * 64,
                service="shop",
                status="running",
                phase="build",
                error=None,
            )
            (root / "operations" / (interrupted["handle"] + ".json")).write_text(
                json.dumps(interrupted)
            )
            recovered = OperationManager(None, root, start_worker=False)
            self.assertEqual(recovered.get(first["handle"])["status"], "queued")
            restored = recovered.get(interrupted["handle"])
            self.assertEqual(restored["status"], "failed")
            self.assertEqual(restored["phase"], "interrupted")
            self.assertIn("inspect service state", restored["error"])

    def test_source_change_during_fake_build_aborts_before_activation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server").mkdir()
            (root / "compose.yaml").write_text("services: {}\n")
            source = root / "server" / "module.py"
            source.write_text("ORIGINAL = True\n")

            class FakeDockerControl(DockerControl):
                def __init__(self):
                    super().__init__(
                        root,
                        "wakfu-local",
                        root / "data",
                        runner=lambda *_a, **_k: None,
                    )
                    self.activated = []

                def container(self, name):
                    return {
                        "id": "fake-container",
                        "state": {"Status": "running"},
                        "image": "fake:image",
                    }

                def configure_build(self):
                    pass

                def build(self, names):
                    self.asserted = names
                    source.write_text("CHANGED_DURING_BUILD = True\n")

                def activate(self, name, force=False):
                    self.activated.append((name, force))

                def wait_healthy(self, name, timeout=240):
                    raise AssertionError("Must abort before health polling")

            control = FakeDockerControl()
            phases = []
            with self.assertRaisesRegex(RuntimeError, "source changed during build"):
                control.restart("shop", phases.append)
            self.assertEqual(control.activated, [])
            self.assertNotIn("restart_shop", phases)
            self.assertEqual(control.asserted, ["shop"])

    def test_compose_project_and_service_allowlist_are_strict(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "server").mkdir()
            (root / "compose.yaml").write_text("services: {}\n")
            with self.assertRaises(ValueError):
                DockerControl(root, "../wakfu", root / "data")
            control = DockerControl(
                root, "wakfu-local", root / "data", runner=lambda *_a, **_k: None
            )
            with self.assertRaises(ValueError):
                control.container("postgres")
            self.assertEqual(control.project, "wakfu-local")

    def test_control_http_requires_bearer_and_broker_allowlist(self):
        class FakeControl:
            @staticmethod
            def services():
                return [
                    {
                        "name": "world",
                        "status": "healthy",
                        "ok": True,
                        "restartable": True,
                    }
                ]

        with tempfile.TemporaryDirectory() as temporary:
            manager = OperationManager(FakeControl(), temporary, start_worker=False)
            server = make_server(
                manager, "token-with-at-least-32-characters-long", "127.0.0.1", 0
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            base = "http://127.0.0.1:%s" % server.server_port

            def request(method, path, *, token=None, body=None):
                headers = {}
                payload = None
                if token is not None:
                    headers["Authorization"] = "Bearer " + token
                if body is not None:
                    headers["Content-Type"] = "application/json"
                    payload = json.dumps(body).encode()
                req = urllib.request.Request(
                    base + path, data=payload, headers=headers, method=method
                )
                try:
                    response = urllib.request.urlopen(req, timeout=5)
                except urllib.error.HTTPError as error:
                    return error.code, json.loads(error.read())
                with response:
                    return response.code, json.loads(response.read())

            status, _ = request("GET", "/services", token="wrong-token")
            self.assertEqual(status, 401)
            status, services = request(
                "GET", "/services", token="token-with-at-least-32-characters-long"
            )
            self.assertEqual(status, 200)
            self.assertEqual("world", services["items"][0]["name"])
            status, _ = request(
                "POST",
                "/restart",
                token="token-with-at-least-32-characters-long",
                body={"service": "postgres", "request_id": "request_123456"},
            )
            self.assertEqual(status, 400)
            status, receipt = request(
                "POST",
                "/restart",
                token="token-with-at-least-32-characters-long",
                body={"service": "world", "request_id": "request_123456"},
            )
            self.assertEqual(status, 200)
            self.assertEqual("queued", receipt["status"])


if __name__ == "__main__":
    unittest.main()
