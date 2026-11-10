"""Real HTTP readiness rejects unavailable fulfillment catalogs and recovers."""

import importlib.util
import json
from pathlib import Path
import sys
import threading
from types import ModuleType, SimpleNamespace
import unittest
from unittest.mock import Mock, patch
import urllib.error
import urllib.request

import wakfu_server

SPEC = importlib.util.spec_from_file_location(
    "shop_service_readiness",
    Path(__file__).resolve().parents[1] / "shop-service" / "readiness.py",
)
readiness = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(readiness)


class ShopReadinessTests(unittest.TestCase):
    def test_health_tracks_catalog_loss_and_recovery_without_hiding_catalog_routes(
        self,
    ):
        domain = SimpleNamespace(catalog=lambda: [], categories=lambda: [])
        check = Mock(return_value="a" * 64)
        server = readiness.make_ready_server(domain, "127.0.0.1", 0, check=check)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(thread.join, 2)
        self.addCleanup(server.server_close)
        self.addCleanup(server.shutdown)
        base = "http://127.0.0.1:%s" % server.server_port

        def request(path="/health", method="GET"):
            req = urllib.request.Request(base + path, method=method)
            try:
                response = urllib.request.urlopen(req, timeout=3)
            except urllib.error.HTTPError as error:
                response = error
            with response:
                return response.code, response.headers, response.read()

        status, headers, body = request()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["catalog_generation"], "a" * 64)
        self.assertEqual(headers["Cache-Control"], "no-store")
        check.side_effect = RuntimeError("No unique complete compiled publication")
        with self.assertLogs(readiness.LOG, level="ERROR"):
            status, _, body = request()
        self.assertEqual(status, 503)
        self.assertEqual(json.loads(body), {"status": "unavailable"})
        self.assertNotIn(b"compiled publication", body)
        status, _, body = request("/en/shops/WAKFU_INGAME/articles")
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body), {"count": 0, "values": []})
        check.side_effect = None
        check.return_value = "b" * 64
        status, _, body = request()
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(body)["catalog_generation"], "b" * 64)
        status, headers, body = request(method="HEAD")
        self.assertEqual(status, 200)
        self.assertEqual(body, b"")
        self.assertGreater(int(headers["Content-Length"]), 0)

    def test_fulfillment_readiness_resolves_publication_and_reads_real_binding_path(
        self,
    ):
        native = ModuleType("wakfu_server.native_catalog")
        native.release = Mock(return_value="source-release")
        compiled = ModuleType("wakfu_server.native_compiled_catalog")
        compiled.resolve_publication = Mock(return_value={"generation": "generation"})
        items = ModuleType("wakfu_server.inventory_items")
        items.grant = Mock()
        delivery = ModuleType("wakfu_server.combat_drop_delivery")
        delivery._template_binding = Mock(return_value=("NOT_BOUND", 0, False))
        modules = {
            module.__name__: module for module in (native, compiled, items, delivery)
        }
        domain = SimpleNamespace(
            public_catalog=Mock(return_value={"articles": [{"item_ref": 2021}]})
        )
        with patch.dict(sys.modules, modules), patch.object(
            wakfu_server, "native_catalog", native, create=True
        ):
            self.assertEqual(readiness.validate_fulfillment(domain), "generation")
            compiled.resolve_publication.assert_called_once_with(
                source_revision="source-release"
            )
            delivery._template_binding.assert_called_once_with(2021)
            items.grant.assert_not_called()
            compiled.resolve_publication.side_effect = RuntimeError("mismatch")
            with self.assertRaisesRegex(RuntimeError, "mismatch"):
                readiness.validate_fulfillment(domain)
        self.assertEqual(delivery._template_binding.call_count, 1)


if __name__ == "__main__":
    unittest.main()
