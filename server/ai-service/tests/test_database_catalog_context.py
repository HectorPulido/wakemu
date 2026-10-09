"""Database catalogs remain complete after protocol artifact removal."""
from contextlib import contextmanager
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from wakfu_ai.bridge.world_bridge import CompleteContextExporter


class CatalogContextTests(unittest.TestCase):
    def test_missing_protocol_files_are_replaced_by_pinned_database_assets(self):
        raw = b'{"monsters":[]}'
        digest = hashlib.sha256(raw).hexdigest()
        metadata = dict(path="monsters.json", sha256=digest, source_bytes=len(raw))

        class Connection:
            def execute(self, query, args):
                self.query = query
                return self

            def fetchall(self):
                return [metadata]

            def fetchone(self):
                return dict(raw=raw)

        class Database:
            @contextmanager
            def connection(self):
                yield Connection()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            protocol = root / "protocol"
            protocol.mkdir()
            (root / "engine.py").write_text("pass\n")
            with patch("wakfu_server.paths.DATA_ROOT", protocol), patch(
                "wakfu_server.native_catalog.release", return_value="a" * 64
            ), patch("wakfu_server.native_catalog._database", return_value=Database()):
                exporter = CompleteContextExporter(
                    {"catalog": protocol, "server": root}
                )
                manifest, sources = exporter.inventory()
                names = {entry["path"] for entry in manifest["entries"]}
                self.assertIn("catalog/monsters.json", names)
                self.assertIn("server/protocol/monsters.json", names)
                with sources[digest].open("rb") as stream:
                    self.assertEqual(stream.read(), raw)

    def test_source_only_does_not_query_database(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "engine.py").write_text("pass\n")
            with patch(
                "wakfu_server.native_catalog.release", side_effect=AssertionError
            ):
                manifest, _ = CompleteContextExporter(
                    {"server": root}, source_only=True
                ).inventory()
            self.assertEqual(len(manifest["entries"]), 1)
