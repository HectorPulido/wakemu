"""Staged cold-start readiness checks using actual immutable ContextStore seals."""
from contextlib import redirect_stdout
from copy import deepcopy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from wakfu_ai.context.context_store import ContextStore

_STAGE = Path(__file__).resolve().parents[1] / "wakfu_ai" / "transport"


def load_staged(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


readiness = load_staged("_staged_catalog_readiness", _STAGE / "startup_readiness.py")
with patch.dict(sys.modules, {"wakfu_ai.transport.startup_readiness": readiness}):
    server = load_staged(
        "wakfu_ai.transport._staged_framed_server", _STAGE / "framed_server.py"
    )


class StartupCatalogReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.store = ContextStore(self.root / "blobs")
        self.addCleanup(self.store.close)
        self.asset = b"complete immutable native asset"
        self.source = b"old source"
        self.asset_digest = self.put(self.asset)
        self.source_digest = self.put(self.source)
        self.entries = [
            dict(
                path="catalog/native.bin",
                sha256=self.asset_digest,
                size=len(self.asset),
            ),
            dict(
                path="server/source.py",
                sha256=self.source_digest,
                size=len(self.source),
            ),
        ]
        self.manifest_digest = self.manifest(self.entries)
        self.descriptor = dict(
            sha256=self.manifest_digest,
            entries=2,
            bytes=len(self.asset) + len(self.source),
        )
        self.file = self.root / "bootstrap.json"
        self.file.write_text(json.dumps(self.descriptor))

    def put(self, raw):
        digest = hashlib.sha256(raw).hexdigest()
        self.store.put(digest, len(raw), 0, raw)
        return digest

    def manifest(self, entries):
        return self.put(
            json.dumps(
                dict(format="wakfu-complete-context-1", entries=entries)
            ).encode()
        )

    def test_main_seals_the_serving_store_before_binding_health_or_decisions(self):
        events = []
        original = self.store.seal_manifest
        store = self.store

        def seal(digest):
            events.append("seal")
            return original(digest)

        class Listener:
            def __init__(self, address):
                events.append("bind")
                self.assert_store = server.http.context_store()
                if (
                    self.assert_store is not store
                    or not store._sealed[self_digest]["ready"]
                ):
                    raise AssertionError("Serving store was not sealed before binding")

            def serve_forever(self):
                events.append("healthy")
                if server.dispatch("/health", {})[0] != 200:
                    raise AssertionError("Prepared health endpoint is unavailable")

            def server_close(self):
                events.append("close")

        self_digest = self.manifest_digest
        with patch.object(server.http, "_CONTEXT_STORE", store), patch.object(
            store, "seal_manifest", side_effect=seal
        ), patch.object(server, "FramedServer", Listener), patch.dict(
            os.environ, {"WAKFU_AI_BOOTSTRAP_MANIFEST": str(self.file)}
        ), redirect_stdout(
            io.StringIO()
        ) as output:
            server.main()
        self.assertEqual(events, ["seal", "bind", "healthy", "close"])
        self.assertEqual(json.loads(output.getvalue())["catalogSha256"], self_digest)

    def test_repeated_world_manifest_uses_the_same_store_snapshot_once(self):
        with patch.object(
            self.store, "_capture_manifest", wraps=self.store._capture_manifest
        ) as capture:
            receipt = readiness.seal_bootstrap_catalog(self.store, self.file)
            self.store.seal_manifest(self.manifest_digest)
            self.assertEqual(capture.call_count, 1)
        self.assertEqual(receipt["catalogSha256"], self.manifest_digest)
        self.assertEqual(
            self.store.read_catalog(self.manifest_digest, self.asset_digest), self.asset
        )

    def test_world_source_delta_reuses_verified_asset_without_rereading_it(self):
        readiness.seal_bootstrap_catalog(self.store, self.file)
        changed = b"new exact World source"
        entries = deepcopy(self.entries)
        entries[1].update(sha256=self.put(changed), size=len(changed))
        delta = self.manifest(entries)
        self.assertNotEqual(delta, self.manifest_digest)
        original = Path.open
        asset_path = self.store._path(self.asset_digest)

        def guarded(path, *args, **kwargs):
            if path == asset_path:
                raise AssertionError(
                    "Verified base asset was reread during World delta sealing"
                )
            return original(path, *args, **kwargs)

        with patch.object(Path, "open", guarded):
            sealed = self.store.seal_manifest(delta)
        self.assertTrue(sealed["complete"])
        self.assertEqual(self.store.read_catalog(delta, self.asset_digest), self.asset)
        self.assertEqual(self.store.read_catalog(delta, entries[1]["sha256"]), changed)

    def test_missing_or_corrupt_catalogue_never_binds_a_listener(self):
        for corrupt in (False, True):
            with self.subTest(corrupt=corrupt):
                asset_path = self.store._path(self.asset_digest)
                if corrupt:
                    asset_path.write_bytes(b"x" * len(self.asset))
                else:
                    asset_path.unlink()
                with patch.object(
                    server.http, "_CONTEXT_STORE", self.store
                ), patch.object(server, "FramedServer") as listener, patch.dict(
                    os.environ, {"WAKFU_AI_BOOTSTRAP_MANIFEST": str(self.file)}
                ):
                    with self.assertRaises(ValueError):
                        server.main()
                    listener.assert_not_called()
                asset_path.write_bytes(self.asset)

    def test_deferred_or_malformed_descriptor_cannot_announce_readiness(self):
        for changed in (
            dict(catalog_deferred=True),
            dict(sha256="foreign"),
            dict(entries=True),
            dict(bytes=-1),
        ):
            with self.subTest(changed=changed):
                descriptor = dict(self.descriptor, **changed)
                self.file.write_text(json.dumps(descriptor))
                with self.assertRaises(ValueError):
                    readiness.seal_bootstrap_catalog(self.store, self.file)

    def test_descriptor_count_must_match_the_complete_verified_manifest(self):
        self.file.write_text(json.dumps(dict(self.descriptor, entries=3)))
        with self.assertRaisesRegex(ValueError, "not completely sealed"):
            readiness.seal_bootstrap_catalog(self.store, self.file)


if __name__ == "__main__":
    unittest.main()
