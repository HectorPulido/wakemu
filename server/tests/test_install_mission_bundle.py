"""Source confinement and all-or-nothing mission bundle publication."""

from contextlib import contextmanager
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from tools import install_mission_bundle as bundle


class BundleSourceTests(unittest.TestCase):
    def test_source_quest_uses_pinned_native_revision_and_shared_transaction(self):
        document = {"sources": []}
        db = object()
        with patch(
            "wakfu_server.achievements.source_quest_encounters.publish",
            return_value={"sources": 7},
        ) as publish:
            result = bundle._publish_entry(
                db,
                {
                    "kind": "source_quest",
                    "document": document,
                    "native_revision": "a" * 64,
                },
            )
        publish.assert_called_once_with(db, document, "a" * 64)
        self.assertEqual(result, {"sources": 7})

    def test_mercenary_board_uses_fixed_settings_publisher_in_same_transaction(self):
        document = {"schema": "reviewed-board", "boards": []}
        db = object()
        with patch(
            "wakfu_server.mercenary_boards.install", return_value={"boards": 2}
        ) as install:
            result = bundle._publish_entry(
                db, {"kind": "mercenary_board", "document": document}
            )
        install.assert_called_once_with(db, document)
        self.assertEqual(result, {"boards": 2})
        self.assertIn("mercenary_board", bundle.KINDS)

    def test_owned_instance_uses_existing_validated_transaction_publisher(self):
        document = {"route": {"key": "reviewed-quest-room"}, "version": 1}
        entry = {"kind": "owned_instance", "document": document}
        db = object()
        with patch(
            "wakfu_server.dungeon_runtime_config.install_configuration",
        ) as install:
            result = bundle._publish_entry(db, entry)
        install.assert_called_once_with(db, document)
        self.assertEqual(result["route_key"], "reviewed-quest-room")
        self.assertIn("owned_instance", bundle.KINDS)

    def test_local_connection_accepts_dsn_and_url_but_rejects_remote_hostaddr(self):
        for dsn in (
            "host=127.0.0.1 port=15432 dbname=wakemu_runtime user=wakemu",
            "postgresql://wakemu@localhost:15432/wakemu_runtime",
        ):
            self.assertEqual(bundle.local_connection(dsn)["port"], "15432")
        for dsn in (
            "host=192.168.0.7 dbname=wakemu_runtime",
            "host=localhost hostaddr=192.168.0.7 dbname=wakemu_runtime",
            "host=localhost,192.168.0.7 dbname=wakemu_runtime",
        ):
            with self.assertRaises(ValueError):
                bundle.local_connection(dsn)

    def test_source_path_and_digest_cannot_escape_reviewed_server_tree(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "server"
            root.mkdir()
            raw = b'{"reviewed":true}'
            (root / "source.json").write_bytes(raw)
            manifest = {
                "schema": bundle.SCHEMA,
                "id": "test",
                "native_metadata_revision": "a" * 64,
                "minimum_schema": 375,
                "entries": [
                    {
                        "kind": "combat",
                        "path": "source.json",
                        "sha256": sha256(raw).hexdigest(),
                    }
                ],
            }
            path = root / "bundle.json"
            path.write_text(json.dumps(manifest))
            self.assertEqual(
                bundle.load_bundle(path, root=root)["entries"][0]["document"],
                {"reviewed": True},
            )
            for invalid in (
                "../source.json",
                str(root / "source.json"),
                "sub\\source.json",
            ):
                manifest["entries"][0]["path"] = invalid
                path.write_text(json.dumps(manifest))
                with self.assertRaises(ValueError):
                    bundle.load_bundle(path, root=root)
            manifest["entries"][0]["path"] = "source.json"
            path.write_text(json.dumps(manifest))
            (root / "source.json").write_bytes(b'{"reviewed":false}')
            with self.assertRaisesRegex(ValueError, "attestation changed"):
                bundle.load_bundle(path, root=root)

    def test_interactive_publisher_receives_only_manifest_pinned_native_revision(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "server"
            root.mkdir()
            source = {"bindings": [{"quest_id": 2048, "objective_id": 4135}]}
            raw = json.dumps(source).encode()
            (root / "interactive.json").write_bytes(raw)
            revision = "b" * 64
            manifest = {
                "schema": bundle.SCHEMA,
                "id": "pinned-interaction",
                "native_metadata_revision": revision,
                "minimum_schema": 378,
                "entries": [
                    {
                        "kind": "interactive",
                        "path": "interactive.json",
                        "sha256": sha256(raw).hexdigest(),
                    }
                ],
            }
            path = root / "bundle.json"
            path.write_text(json.dumps(manifest))
            loaded = bundle.load_bundle(path, root=root)
            entry = loaded["entries"][0]
            self.assertEqual(revision, entry["native_revision"])
            self.assertEqual(
                {"kind", "path", "sha256", "document", "native_revision"},
                set(entry),
            )

            db = object()
            with patch(
                "tools.install_quest_interactions.install", return_value=["installed"]
            ) as install:
                result = bundle._publish_entry(db, entry)
            install.assert_called_once_with(db, source, revision)
            self.assertEqual({"bindings": ["installed"]}, result)

            for extra in (
                {"native_revision": "c" * 64},
                {"callback": "arbitrary"},
            ):
                invalid = deepcopy(manifest)
                invalid["entries"][0].update(extra)
                path.write_text(json.dumps(invalid))
                with self.subTest(extra=extra), self.assertRaisesRegex(
                    ValueError, "Unsupported mission bundle entry"
                ):
                    bundle.load_bundle(path, root=root)


class TransactionDB:
    def __init__(self):
        self.publications = {"existing": "preserved"}

    @contextmanager
    def transaction(self, *, force_rollback=False):
        before = deepcopy(self.publications)
        try:
            yield
        except BaseException:
            self.publications = before
            raise
        finally:
            if force_rollback:
                self.publications = before

    def execute(self, query, params):
        return None


class BundleTransactionTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "id": "two-families",
            "native_metadata_revision": "a" * 64,
            "entries": [
                {"kind": "combat", "path": "combat.json", "document": {"id": "combat"}},
                {
                    "kind": "toolkit",
                    "path": "toolkit.json",
                    "document": {"id": "toolkit"},
                },
            ],
        }

    def publish(self, db, entry):
        db.publications[entry["kind"]] = "published"
        return {"id": entry["kind"]}

    def test_late_failure_rolls_back_earlier_publisher(self):
        db = TransactionDB()

        def late_failure(db, entry):
            self.publish(db, entry)
            if entry["kind"] == "toolkit":
                raise ValueError("conflicting final profile")
            return {}

        with patch.object(bundle, "_preflight"), patch.object(
            bundle, "_publish_entry", side_effect=late_failure
        ):
            with self.assertRaisesRegex(ValueError, "conflicting final profile"):
                bundle.install_bundle(db, self.document, apply=True)
        self.assertEqual(db.publications, {"existing": "preserved"})

    def test_dry_run_exercises_publishers_then_apply_is_idempotent(self):
        db = TransactionDB()
        with patch.object(bundle, "_preflight"), patch.object(
            bundle, "_publish_entry", side_effect=self.publish
        ) as publisher:
            result = bundle.install_bundle(db, self.document)
            self.assertEqual(publisher.call_count, 2)
            self.assertTrue(result["rolled_back"])
            self.assertFalse(result["applied"])
            self.assertEqual(db.publications, {"existing": "preserved"})
            result = bundle.install_bundle(db, self.document, apply=True)
            after = deepcopy(db.publications)
            bundle.install_bundle(db, self.document, apply=True)
        self.assertEqual(db.publications, after)
        self.assertFalse(result["rolled_back"])
        self.assertEqual(
            after,
            {"existing": "preserved", "combat": "published", "toolkit": "published"},
        )


if __name__ == "__main__":
    unittest.main()
