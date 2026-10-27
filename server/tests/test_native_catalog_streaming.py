"""Large-document path preserves legacy raw/index semantics and atomicity."""
import gzip
import hashlib
import json
from pathlib import Path
import tempfile
from unittest.mock import patch

from postgres_case import PostgresCase
from tools import import_native_catalogs as importer
from tools import native_catalog_streaming as streaming


class NativeCatalogStreamingTests(PostgresCase):
    def test_streamed_binary_raw_legacy_keys_snapshot_and_atomic_activation(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        directory = Path(temporary.name)
        fixtures = {
            "items.json": b"\xef\xbb\xbf"
            + (
                '{"items":[{"ref":8,"v":"first"},{"ref":8,"v":"second"},'
                '{"ref":"8@0","v":"literal-zero"},{"ref":"8@1","v":"literal-one"}],'
                '"objects":{"x":{"v":1},"x":{"v":2}},'
                '"repeat":{"gone":42},"repeat":[{"id":3}],'
                '"numbers":[12345678901234567890123456789012345678901234567890,1.2e-7,-0.0,true,null],'
                '"unicode":{"déjà":"漢字"},"cells":[{"ignored":true}]}'
            ).encode("utf8"),
            "array.json": b'[true,12,{"id":99},{"id":99},{"id":"99@2"}]',
            "odd\tunicodeé.json": b'{"collection.with.dot":{"item.with.dot":{"ok":true}}}',
            "combat-maps/fixture.json": b'{"cells":[[1,2,3]],"meta":{"raw":"kept"}}',
        }
        pack = Path(__file__).resolve().parents[1] / "data/installation/catalogs"
        manifest = json.loads((pack / "manifest.json").read_bytes())
        release = next(
            row
            for row in manifest["releases"]
            if row["revision"] == manifest["active_revision"]
        )
        real_source = next(
            row
            for row in release["documents"]
            if row["path"] == "item-equipment-rules.json"
        )
        real_raw = b"".join(
            gzip.decompress((pack / part["path"]).read_bytes())
            for part in manifest["blobs"][real_source["sha256"]]["parts"]
        )
        self.assertEqual(hashlib.sha256(real_raw).hexdigest(), real_source["sha256"])
        fixtures["original-equipment-rules.json"] = real_raw
        expected = {}
        for name, raw in fixtures.items():
            target = directory / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(raw)
            expected[name] = sorted(importer.catalog_records(name, json.loads(raw)))
        with patch.object(importer, "STREAM_DOCUMENT_BYTES", 1):
            result = importer.import_catalogs(self.store, directory)
        self.assertTrue(result["activated"])
        self.assertEqual(result["records"], sum(map(len, expected.values())))
        with self.store.connection() as db:
            for name, raw in fixtures.items():
                document = db.execute(
                    "SELECT raw,sha256,source_bytes,record_count FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (result["revision"], name),
                ).fetchone()
                self.assertEqual(bytes(document["raw"]), raw)
                self.assertEqual(document["sha256"], hashlib.sha256(raw).hexdigest())
                self.assertEqual(document["source_bytes"], len(raw))
                self.assertEqual(document["record_count"], len(expected[name]))
                rows = db.execute(
                    "SELECT collection,record_key,payload FROM native_catalog_records WHERE revision=%s AND path=%s ORDER BY collection,record_key",
                    (result["revision"], name),
                ).fetchall()
                self.assertEqual(
                    [(r["collection"], r["record_key"], r["payload"]) for r in rows],
                    expected[name],
                )
        with patch.object(importer, "STREAM_DOCUMENT_BYTES", 1):
            replay = importer.import_catalogs(self.store, directory)
        self.assertEqual(replay["skipped"], len(fixtures))
        self.assertEqual(replay["imported"], 0)
        old_revision = result["revision"]

        # An error after raw COPY rolls back that document and all its index
        # rows. The previous complete publication remains selected.
        broken_directory = directory / "broken-only"
        broken_directory.mkdir()
        target = broken_directory / "zz-broken.json"
        target.write_bytes(b'{"items":{"42":')
        with patch.object(importer, "STREAM_DOCUMENT_BYTES", 1):
            with self.assertRaises(Exception):
                importer.import_catalogs(self.store, broken_directory)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM native_catalog_active WHERE id=1"
                ).fetchone()["revision"],
                old_revision,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_documents WHERE path=%s",
                    (target.name,),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_records WHERE path=%s",
                    (target.name,),
                ).fetchone()["n"],
                0,
            )
        target.unlink()

        # Both raw and indexed payloads consume one verified disk snapshot,
        # even if the caller's source changes during the database operation.
        snapshot_directory = directory / "snapshot-only"
        snapshot_directory.mkdir()
        snapshot_path = snapshot_directory / "one.json"
        original = b'{"items":{"42":{"id":42,"v":"original"}}}'
        snapshot_path.write_bytes(original)
        original_copy = streaming.copy_raw_document

        def mutate_source_after_copy(*args):
            original_copy(*args)
            snapshot_path.write_bytes(b'{"items":{"99":{"id":99,"v":"changed"}}}')

        with patch.object(importer, "STREAM_DOCUMENT_BYTES", 1), patch.object(
            streaming, "copy_raw_document", side_effect=mutate_source_after_copy
        ):
            frozen = importer.import_catalogs(self.store, snapshot_directory)
        with self.store.connection() as db:
            document = db.execute(
                "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (frozen["revision"], "one.json"),
            ).fetchone()
            self.assertEqual(bytes(document["raw"]), original)
            row = db.execute(
                "SELECT record_key,payload FROM native_catalog_records WHERE revision=%s",
                (frozen["revision"],),
            ).fetchone()
            self.assertEqual(
                row, dict(record_key="42", payload=dict(id=42, v="original"))
            )

        # A failure while writing derived entities has the same transaction
        # boundary as the legacy importer: staged raw is never left orphaned.
        failing_directory = directory / "rejected-only"
        failing_directory.mkdir()
        (failing_directory / "rejected.json").write_bytes(
            b'{"items":{"666":{"id":666}}}'
        )
        with self.store.connection() as db:
            db.execute(
                "CREATE FUNCTION reject_streamed_test_row() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN IF NEW.record_key='666' THEN RAISE EXCEPTION 'intentional streamed record failure'; END IF; RETURN NEW; END; $$"
            )
            db.execute(
                "CREATE TRIGGER reject_streamed_test_row BEFORE INSERT ON native_catalog_records FOR EACH ROW EXECUTE FUNCTION reject_streamed_test_row()"
            )
        with patch.object(importer, "STREAM_DOCUMENT_BYTES", 1):
            with self.assertRaisesRegex(
                Exception, "intentional streamed record failure"
            ):
                importer.import_catalogs(self.store, failing_directory)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM native_catalog_active WHERE id=1"
                ).fetchone()["revision"],
                frozen["revision"],
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM native_catalog_documents WHERE path='rejected.json'"
                ).fetchone()["n"],
                0,
            )
