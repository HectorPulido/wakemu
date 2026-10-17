"""Published-only reader forbids filesystem fallback and preserves offline replay."""
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from types import SimpleNamespace

from wakfu_server import native_catalog
from wakfu_server.combat_reproduction_catalog import (
    CaptureCatalog,
    ReplayCatalog,
    MissingReproductionCatalog,
)

_STRICT_ALIAS = native_catalog.read_published_bytes


class PublishedCatalogReaderTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        (root / "catalog.json").write_bytes(b'{"local":true}')
        database, redis = MagicMock(), MagicMock()
        redis.get.return_value = None
        self.fixture = SimpleNamespace(database=database, redis=redis)
        for name, value in (
            ("DATA_ROOT", root),
            ("_database", lambda: database),
            ("_redis", lambda: redis),
            ("release", lambda: "rev-17"),
        ):
            context = patch.object(native_catalog, name, value)
            context.start()
            self.addCleanup(context.stop)

        def set_document(raw):
            cursor, connection = MagicMock(), MagicMock()
            cursor.fetchone.return_value = {
                "raw": raw,
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            connection.__enter__.return_value = connection
            connection.__exit__.return_value = False
            connection.execute.return_value = cursor
            database.connection.return_value = connection
            return cursor

        self.fixture.set_document = set_document

    def test_invalid_logical_names_never_touch_database_or_filesystem(self):
        with patch.object(
            native_catalog, "_database", side_effect=AssertionError("database touched")
        ), patch.object(Path, "read_bytes", side_effect=AssertionError("file touched")):
            for name in (
                "/tmp/a",
                "../a",
                "a/../b",
                "a//b",
                "./a",
                "a\\b",
                "a\0b",
                "",
                Path("a"),
            ):
                with self.subTest(name=name), self.assertRaises(ValueError):
                    native_catalog.read_published_bytes(name)

    def test_published_logical_name_reads_database_not_existing_local_file(self):
        raw = b'{"published":true}'
        self.fixture.set_document(raw)
        with patch.object(
            Path, "read_bytes", side_effect=AssertionError("filesystem fallback")
        ):
            self.assertEqual(native_catalog.read_published_bytes("catalog.json"), raw)

    def test_unpublished_name_does_not_read_matching_local_file_or_redis(self):
        cursor = self.fixture.set_document(b"ignored")
        cursor.fetchone.return_value = None
        with patch.object(
            Path, "read_bytes", side_effect=AssertionError("filesystem fallback")
        ):
            with self.assertRaises(FileNotFoundError):
                native_catalog.read_published_bytes("catalog.json")
        self.fixture.redis.get.assert_not_called()

    def test_self_consistent_wrong_redis_payload_fails_published_sha(self):
        self.fixture.set_document(b'{"published":true}')
        wrong = b'{"wrong":true}'
        self.fixture.redis.get.return_value = (
            hashlib.sha256(wrong).hexdigest().encode() + b"\n" + wrong
        )
        with self.assertRaisesRegex(ValueError, "identity changed"):
            native_catalog.read_published_bytes("catalog.json")

    def test_changed_release_cannot_return_mixed_identity(self):
        self.fixture.set_document(b'{"published":true}')
        with patch.object(
            native_catalog, "release", side_effect=["first", "first", "second"]
        ):
            with self.assertRaisesRegex(ValueError, "identity changed"):
                native_catalog.read_published_bytes("catalog.json")

    def test_capture_tracks_real_strict_reader_and_restores_direct_alias(self):
        raw = b'{"published":true}'
        self.fixture.set_document(raw)
        original = _STRICT_ALIAS
        with CaptureCatalog() as capture:
            self.assertEqual(_STRICT_ALIAS("catalog.json"), raw)
            self.assertIn("catalog.json", capture.documents)
            self.assertEqual(
                capture.read_hashes["catalog.json"], hashlib.sha256(raw).hexdigest()
            )
        self.assertIs(_STRICT_ALIAS, original)

    def test_replay_strict_reader_is_offline_and_rejects_unrecorded_member(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            blobs = root / "catalog"
            blobs.mkdir()
            raw = b'{"published":true}'
            records = b"[]"

            def descriptor(value):
                digest = hashlib.sha256(value).hexdigest()
                (blobs / digest).write_bytes(value)
                return dict(sha256=digest, size=len(value))

            doc = descriptor(raw)
            record = descriptor(records)
            manifest = dict(
                version=1,
                authority="postgresql-published-release",
                revision="fixture",
                published_hashes={
                    "catalog.json": doc["sha256"],
                    "unrecorded.json": "a" * 64,
                },
                documents={"catalog.json": doc},
                records=record,
                exists={},
            )
            (root / "catalog.json").write_text(json.dumps(manifest))
            replay = ReplayCatalog(root)
            with patch.object(
                native_catalog,
                "_database",
                side_effect=AssertionError("live DB during replay"),
            ):
                with replay.install():
                    self.assertEqual(
                        native_catalog.read_published_bytes("catalog.json"), raw
                    )
                    with self.assertRaises(MissingReproductionCatalog):
                        native_catalog.read_published_bytes("unrecorded.json")
                    with self.assertRaises(MissingReproductionCatalog):
                        native_catalog.read_published_bytes("unpublished.json")


class PublishedReaderSelectionTests(unittest.TestCase):
    """Synthetic source-bound domain tests, separate from native data execution."""

    def scenario(self, mode):
        from tools import combat_test_impact as impact

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)

            def write(name, value):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(value)

            api = "server/wakfu_server/storage/native_catalog.py"
            body = 'def read_published_bytes(name):\n return b"fixture"\n'
            write(api, body)
            write("server/tools/combat_validation_profile.py", "# fixture\n")
            write("server/wakfu_server/leaf.py", "VALUE=1\n")
            write(
                "server/tools/read_user.py",
                "from wakfu_server import native_catalog\nfrom wakfu_server.leaf import VALUE\ndef read(name):\n return native_catalog.read_published_bytes(name)\n",
            )
            reflected = {
                "reflective-object": "from unittest.mock import patch\npatch.object(native_catalog,'read_published_bytes',fake)\n",
                "reflective-setattr": "setattr(native_catalog,symbol,fake)\n",
                "reflective-path": "from unittest.mock import patch\npatch('wakfu_server.storage.native_catalog.read_published_bytes',fake)\n",
                "reflective-dict": "from unittest.mock import patch\npatch.dict(native_catalog.__dict__,{'read_published_bytes':fake})\n",
                "reflective-dict-update": "native_catalog.__dict__.update({'read_published_bytes':fake})\n",
            }

            write(
                "server/tests/test_read_user.py", "from tools.read_user import read\n"
            )
            write("server/tests/test_unrelated.py", "VALUE=True\n")
            contracts = json.loads(impact.CONTRACTS_PATH.read_text())
            contracts["published_reader_contracts"] = [
                dict(
                    source_path=api,
                    source_sha256=hashlib.sha256(body.encode()).hexdigest(),
                    symbol="read_published_bytes",
                    domain="pinned-published-catalog-only",
                )
            ]
            contract_path = root / "contracts.json"
            contract_path.write_text(json.dumps(contracts))
            catalog = dict(
                status="published",
                revision="fixture",
                documents={"a.json": "a" * 64},
                sha256="a" * 64,
                publication_verified=True,
            )
            with patch.object(impact, "CONTRACTS_PATH", contract_path), patch.object(
                impact, "environment_manifest", return_value={"sha256": "e" * 64}
            ), patch.dict("os.environ", {}, clear=True):
                before = impact.build_graph(root, catalog_inventory=catalog)
                write("server/wakfu_server/leaf.py", "VALUE=2\n")
                if mode in reflected:
                    write(
                        "server/tools/read_user.py",
                        "from wakfu_server import native_catalog\nfrom wakfu_server.leaf import VALUE\n"
                        + reflected[mode]
                        + "def read(name):\n return native_catalog.read_published_bytes(name)\n",
                    )
                if mode == "definition-shadow":
                    write(
                        "server/tools/read_user.py",
                        "from wakfu_server.storage.native_catalog import read_published_bytes\nfrom wakfu_server.leaf import VALUE\ndef read_published_bytes(name):\n return fake(name)\ndef read(name):\n return read_published_bytes(name)\n",
                    )
                if mode == "stale-reader":
                    write(
                        api,
                        "def read_published_bytes(name):\n return Path(name).read_bytes()\n",
                    )
                elif mode == "changed-catalog":
                    catalog = {
                        **catalog,
                        "documents": {"a.json": "b" * 64},
                        "sha256": "b" * 64,
                    }
                elif mode == "unverified-catalog":
                    catalog = {**catalog, "publication_verified": False}
                after = impact.build_graph(root, catalog_inventory=catalog)
                return impact.select_changes(before, after), after

    def test_unchanged_published_domain_retains_only_actual_reader_consumers(self):
        plan, graph = self.scenario("stable")
        self.assertEqual(plan["selected_module_names"], ["test_read_user"])
        self.assertEqual(plan["source_impacted_module_names"], ["test_read_user"])
        self.assertFalse(plan["source_workflow"]["reuse_qualified"])
        self.assertEqual(graph["published_reader_registry"]["errors"], [])
        self.assertTrue(
            any(
                row["reason"] == "published-catalog-domain"
                and row["scope"] == "owner-consumers"
                for row in plan["fallbacks"]
            )
        )

    def test_changed_or_unverified_catalog_still_forces_full_scope(self):
        for mode in ("changed-catalog", "unverified-catalog"):
            with self.subTest(mode=mode):
                plan, _ = self.scenario(mode)
                self.assertEqual(
                    plan["selected_module_names"], ["test_read_user", "test_unrelated"]
                )
                self.assertTrue(
                    any(row["scope"] == "full" for row in plan["fallbacks"])
                )
                self.assertEqual(
                    plan["source_impacted_module_names"], ["test_read_user"]
                )
                self.assertFalse(plan["source_workflow"]["reuse_qualified"])
                self.assertEqual(
                    plan["source_workflow"]["excluded_module_status"],
                    "not-executed-not-reused-not-proven",
                )

    def test_changed_reader_implementation_invalidates_source_bound_contract(self):
        plan, graph = self.scenario("stale-reader")
        self.assertTrue(graph["published_reader_registry"]["errors"])
        self.assertEqual(
            plan["selected_module_names"], ["test_read_user", "test_unrelated"]
        )
        self.assertTrue(
            any(
                row["reason"] == "unqualified-published-reader"
                and row["scope"] == "full"
                for row in plan["fallbacks"]
            )
        )

    def test_visible_reflective_reader_mutations_stay_full_and_unqualified(self):
        for mode in (
            "reflective-object",
            "reflective-setattr",
            "reflective-path",
            "reflective-dict",
            "reflective-dict-update",
            "definition-shadow",
        ):
            with self.subTest(mode=mode):
                plan, _ = self.scenario(mode)
                self.assertEqual(
                    plan["selected_module_names"], ["test_read_user", "test_unrelated"]
                )
                self.assertTrue(
                    any(
                        row["reason"] == "unqualified-published-reader"
                        and row["scope"] == "full"
                        for row in plan["fallbacks"]
                    )
                )
                self.assertFalse(plan["source_workflow"]["reuse_qualified"])
