"""Append-only immutable catalog staging on small isolated PostgreSQL releases."""
import hashlib
import json
import tempfile
from pathlib import Path

from postgres_case import PostgresCase
from tools.extend_native_catalogs import stage_extension
from tools.import_native_catalogs import (
    import_catalogs,
    release_revision,
    source_manifest,
)


class NativeCatalogExtensionPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        (root / "base.json").write_bytes(
            b'{"spells":{"1":{"id":1,"value":"retained"}}}'
        )
        receipt = import_catalogs(self.store.database, root)
        self.base = {"receipt": receipt, "documents": source_manifest(root)}
        self.additions = {
            "native-common-spell-effect-trees.json": b'{"spells":{"5623":{"effects":[1,2]}}}',
            "native-common-spell-casting-roots.json": b'{"roots":[{"spell_id":5623,"effect":9}]}',
        }

    def query(self, sql, params=()):
        with self.store.connection() as db:
            return db.execute(sql, params).fetchall()

    def test_complete_clone_preserves_base_activation_and_is_idempotent(self):
        base_revision = self.base["receipt"]["revision"]
        before = self.query(
            "SELECT * FROM native_catalog_documents WHERE revision=%s", (base_revision,)
        )
        result = stage_extension(self.store.database, self.base, self.additions)
        receipt = result["receipt"]
        self.assertFalse(receipt["activated"])
        self.assertFalse(receipt["reused"])
        self.assertEqual(3, receipt["documents"])
        self.assertEqual(3, receipt["records"])
        self.assertEqual(receipt["revision"], release_revision(result["documents"]))
        self.assertEqual(
            base_revision,
            self.query("SELECT revision FROM native_catalog_active")[0]["revision"],
        )
        self.assertEqual(
            before,
            self.query(
                "SELECT * FROM native_catalog_documents WHERE revision=%s",
                (base_revision,),
            ),
        )
        self.assertTrue(
            self.query(
                "SELECT complete FROM native_catalog_releases WHERE revision=%s",
                (receipt["revision"],),
            )[0]["complete"]
        )
        for path, raw in self.additions.items():
            row = self.query(
                "SELECT raw,sha256 FROM native_catalog_documents WHERE revision=%s AND path=%s",
                (receipt["revision"], path),
            )[0]
            self.assertEqual(raw, bytes(row["raw"]))
            self.assertEqual(hashlib.sha256(raw).hexdigest(), row["sha256"])
        copied = self.query(
            "SELECT payload FROM native_catalog_records WHERE revision=%s AND path=%s",
            (receipt["revision"], "base.json"),
        )
        self.assertEqual([{"payload": {"id": 1, "value": "retained"}}], copied)
        second = stage_extension(self.store.database, self.base, self.additions)
        self.assertTrue(second["receipt"]["reused"])
        self.assertEqual(result["documents"], second["documents"])
        self.assertEqual(
            2, self.query("SELECT count(*) AS n FROM native_catalog_releases")[0]["n"]
        )

    def test_failed_append_rolls_back_entire_clone_without_touching_old_release(self):
        with self.store.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_extension() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.path='native-common-spell-casting-roots.json' THEN
                RAISE EXCEPTION 'intentional extension failure'; END IF; RETURN NEW; END $$"""
            )
            db.execute(
                "CREATE TRIGGER reject_extension BEFORE INSERT ON native_catalog_records FOR EACH ROW EXECUTE FUNCTION reject_extension()"
            )
        with self.assertRaisesRegex(Exception, "intentional extension failure"):
            stage_extension(self.store.database, self.base, self.additions)
        self.assertEqual(
            1, self.query("SELECT count(*) AS n FROM native_catalog_releases")[0]["n"]
        )
        self.assertEqual(
            1, self.query("SELECT count(*) AS n FROM native_catalog_documents")[0]["n"]
        )
        self.assertEqual(
            self.base["receipt"]["revision"],
            self.query("SELECT revision FROM native_catalog_active")[0]["revision"],
        )

    def test_existing_paths_and_false_pinned_manifest_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "already exists"):
            stage_extension(self.store.database, self.base, {"base.json": b"{}"})
        bad = json.loads(json.dumps(self.base))
        bad["documents"][0][2] += 1
        with self.assertRaisesRegex(ValueError, "pinned manifest"):
            stage_extension(self.store.database, bad, self.additions)
        self.assertEqual(
            1, self.query("SELECT count(*) AS n FROM native_catalog_releases")[0]["n"]
        )


class NativeCatalogReplacementPostgresTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        root = Path(self.directory.name)
        self.old = b'{"items":{"1":{"id":1,"enabled":false}}}'
        self.new = b'{"items":{"10":{"id":10,"enabled":true},"11":{"id":11}}}'
        (root / "base.json").write_bytes(self.old)
        (root / "kept.json").write_bytes(b'{"spells":{"7":{"id":7,"unchanged":true}}}')
        self.base = {
            "receipt": import_catalogs(self.store.database, root),
            "documents": source_manifest(root),
        }

    def query(self, sql, params=()):
        with self.store.connection() as db:
            return db.execute(sql, params).fetchall()

    def test_explicit_replacement_reindexes_only_target_and_is_idempotent(self):
        result = stage_extension(
            self.store.database, self.base, {}, replacements={"base.json": self.new}
        )
        revision = result["receipt"]["revision"]
        self.assertEqual(
            (2, 3, 1, 0),
            tuple(
                result["receipt"][k]
                for k in (
                    "documents",
                    "records",
                    "replaced_documents",
                    "added_documents",
                )
            ),
        )
        self.assertEqual(revision, release_revision(result["documents"]))
        self.assertEqual(
            self.base["receipt"]["revision"],
            self.query("SELECT revision FROM native_catalog_active")[0]["revision"],
        )
        self.assertEqual(
            self.old,
            bytes(
                self.query(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (self.base["receipt"]["revision"], "base.json"),
                )[0]["raw"]
            ),
        )
        self.assertEqual(
            self.new,
            bytes(
                self.query(
                    "SELECT raw FROM native_catalog_documents WHERE revision=%s AND path=%s",
                    (revision, "base.json"),
                )[0]["raw"]
            ),
        )
        records = self.query(
            "SELECT path,record_key,payload FROM native_catalog_records WHERE revision=%s ORDER BY path,record_key",
            (revision,),
        )
        self.assertEqual(
            [("base.json", "10"), ("base.json", "11"), ("kept.json", "7")],
            [(r["path"], r["record_key"]) for r in records],
        )
        self.assertEqual({"id": 7, "unchanged": True}, records[-1]["payload"])
        second = stage_extension(
            self.store.database, self.base, {}, replacements={"base.json": self.new}
        )
        self.assertTrue(second["receipt"]["reused"])
        self.assertEqual(result["documents"], second["documents"])
        self.assertEqual(
            2, self.query("SELECT count(*) AS n FROM native_catalog_releases")[0]["n"]
        )

    def test_failed_replacement_rolls_back_complete_clone_and_keeps_activation(self):
        with self.store.connection() as db:
            db.execute(
                """CREATE FUNCTION reject_replacement() RETURNS trigger LANGUAGE plpgsql AS $$
                BEGIN IF NEW.path='base.json' AND NEW.record_key='11' THEN
                RAISE EXCEPTION 'intentional replacement failure'; END IF; RETURN NEW; END $$"""
            )
            db.execute(
                "CREATE TRIGGER reject_replacement BEFORE INSERT ON native_catalog_records FOR EACH ROW EXECUTE FUNCTION reject_replacement()"
            )
        with self.assertRaisesRegex(Exception, "intentional replacement failure"):
            stage_extension(
                self.store.database, self.base, {}, replacements={"base.json": self.new}
            )
        self.assertEqual(
            1, self.query("SELECT count(*) AS n FROM native_catalog_releases")[0]["n"]
        )
        self.assertEqual(
            2, self.query("SELECT count(*) AS n FROM native_catalog_documents")[0]["n"]
        )
        self.assertEqual(
            2, self.query("SELECT count(*) AS n FROM native_catalog_records")[0]["n"]
        )
        self.assertEqual(
            self.base["receipt"]["revision"],
            self.query("SELECT revision FROM native_catalog_active")[0]["revision"],
        )

    def test_replacement_is_explicit_and_default_append_collision_guard_still_holds(
        self,
    ):
        with self.assertRaisesRegex(ValueError, "already exists"):
            stage_extension(self.store.database, self.base, {"base.json": self.new})
        with self.assertRaisesRegex(ValueError, "absent from base"):
            stage_extension(
                self.store.database,
                self.base,
                {},
                replacements={"missing.json": self.new},
            )
        with self.assertRaisesRegex(ValueError, "both added"):
            stage_extension(
                self.store.database,
                self.base,
                {"base.json": self.new},
                replacements={"base.json": self.new},
            )
        # Exercise the unchanged append API with its now-empty exclusion list.
        added = stage_extension(
            self.store.database, self.base, {"extra.json": b'{"roots":[1]}'}
        )
        self.assertEqual(
            (3, 1, 0),
            tuple(
                added["receipt"][k]
                for k in ("documents", "added_documents", "replaced_documents")
            ),
        )
