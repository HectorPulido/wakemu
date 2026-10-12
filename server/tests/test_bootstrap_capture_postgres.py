"""Isolated database authority preserves the complete ordered frame bootstrap."""
from postgres_case import PostgresCase
from test_bootstrap_capture import frames
from wakfu_server.storage import bootstrap_capture as capture


class BootstrapCapturePostgresTests(PostgresCase):
    def test_import_roundtrip_idempotent_readonly_load_and_conflict(self):
        original = frames()
        with self.store.connection() as db:
            with self.assertRaises(ValueError):
                capture.load(db)
            self.assertTrue(
                capture.import_records(db, capture.DEFAULT_KEY, "a" * 64, original)
            )
            self.assertFalse(
                capture.import_records(db, capture.DEFAULT_KEY, "a" * 64, original)
            )
        with self.store.connection() as db:
            db.execute("SET TRANSACTION READ ONLY")
            self.assertEqual(
                capture.load(db, expected_source_sha256="a" * 64), original
            )
        changed = frames()
        changed[0]["opcode"] = 2
        with self.assertRaises(ValueError), self.store.connection() as db:
            capture.import_records(db, capture.DEFAULT_KEY, "b" * 64, changed)
        with self.assertRaises(ValueError), self.store.connection() as db:
            capture.load(db, expected_source_sha256="b" * 64)

    def test_missing_corrupt_or_reordered_records_fail_closed(self):
        with self.store.connection() as db:
            capture.import_records(db, capture.DEFAULT_KEY, "a" * 64, frames())
        mutations = [
            "DELETE FROM bootstrap_capture_records WHERE ordinal=0",
            "UPDATE bootstrap_capture_records SET ordinal=100 WHERE ordinal=0",
            "UPDATE bootstrap_capture_records SET payload=jsonb_set(payload,'{opcode}','2') WHERE ordinal=0",
            "UPDATE bootstrap_capture_manifests SET content_sha256=repeat('b',64)",
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation), self.assertRaises(
                ValueError
            ), self.store.connection() as db:
                db.execute(mutation)
                capture.load(db)
        with self.store.connection() as db:
            self.assertEqual(capture.load(db), frames())

    def test_enclosing_rollback_leaves_no_partial_manifest_or_records(self):
        with self.assertRaises(RuntimeError), self.store.connection() as db:
            capture.import_records(db, capture.DEFAULT_KEY, "a" * 64, frames())
            raise RuntimeError("Simulated import transaction failure")
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM bootstrap_capture_manifests"
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM bootstrap_capture_records"
                ).fetchone()["n"],
                0,
            )
