"""Read-only staging and immutable manifest regressions."""
from contextlib import nullcontext
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).parents[1] / "tools"))
import stage_mining_navigation_catalog as staging


class FakeConnection:
    def __init__(self, revision="base", existing=None):
        self.revision, self.existing, self.sql = revision, existing, []

    def transaction(self):
        return nullcontext()

    def execute(self, sql, parameters=None):
        self.sql.append(sql)
        self.current = sql
        return self

    def fetchone(self):
        if "native_catalog_active" in self.current:
            return (self.revision,)
        return self.existing

    def fetchall(self):
        return [("untouched.json", "a" * 64, 99)]


class NavigationStagingTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        self.document = dict(
            map_id=1,
            profile="native_world_exploration_4_0_6",
            cells=[[0, 0, 0]],
            resource_approaches=[
                dict(
                    position=[1, 0, 0],
                    approaches=[[0, 0, 0]],
                    ground_id=1,
                    eligible_refs=[20],
                )
            ],
            provenance=dict(
                source="installed-client",
                client_sha256="a" * 64,
                topology_sha256="b" * 64,
                approach_authority="cWn.gu:VF.a:profession73",
            ),
        )
        self.write()

    def write(self):
        (self.root / "1.json").write_text(json.dumps(self.document))

    def test_default_dry_run_is_read_only_and_never_changes_active(self):
        connection = FakeConnection()
        result = staging.stage(connection, self.root, "base")
        self.assertTrue(result["dry_run"])
        self.assertFalse(result["activated"])
        self.assertFalse(result["staged"])
        self.assertEqual(result["documents"], 2)
        self.assertEqual(connection.sql[0], "SET TRANSACTION READ ONLY")
        self.assertFalse(
            any(
                "INSERT" in sql or "UPDATE" in sql or "FOR SHARE" in sql
                for sql in connection.sql
            )
        )

    def test_changed_active_revision_fails_before_any_write(self):
        connection = FakeConnection(revision="other")
        with self.assertRaisesRegex(ValueError, "changed"):
            staging.stage(connection, self.root, "base", dry_run=False)
        self.assertFalse(
            any("INSERT" in sql or "UPDATE" in sql for sql in connection.sql)
        )

    def test_full_manifest_preserves_every_unrelated_document(self):
        exported = staging.documents(self.root)
        manifest = staging.full_manifest(
            [("untouched.json", "a" * 64, 99), ("world-navigation/1.json", "old", 1)],
            exported,
        )
        self.assertIn(("untouched.json", "a" * 64, 99), manifest)
        self.assertEqual(len(manifest), 2)
        self.assertEqual(
            staging.release_revision(manifest), staging.release_revision(list(manifest))
        )

    def test_native_mineral_approach_must_validate(self):
        self.document["resource_approaches"][0]["approaches"] = [[5, 0, 0]]
        self.write()
        with self.assertRaisesRegex(ValueError, "walkable"):
            staging.documents(self.root)

    def test_mismatched_map_filename_and_incomplete_release_rejected(self):
        self.document["map_id"] = 2
        self.write()
        with self.assertRaisesRegex(ValueError, "map mismatch"):
            staging.documents(self.root)
        self.document["map_id"] = 1
        self.write()
        with self.assertRaisesRegex(ValueError, "incomplete"):
            staging.stage(FakeConnection(existing=(False,)), self.root, "base")

    def test_index_is_not_treated_as_navigation_map(self):
        (self.root / "index.json").write_text('{"metadata": true}')
        self.assertEqual(len(staging.documents(self.root)), 1)

    def test_explicit_staging_copies_unrelated_documents_and_records_without_activation(
        self,
    ):
        class Writer:
            def __init__(self):
                self.rows = []

            def write_row(self, row):
                self.rows.append(row)

        class StagingConnection(FakeConnection):
            def __init__(inner):
                super().__init__()
                inner.writer = Writer()
                inner.manifests_read = 0

            def fetchall(inner):
                inner.manifests_read += 1
                if inner.manifests_read == 1:
                    return super().fetchall()
                return staging.full_manifest(
                    super().fetchall(), staging.documents(self.root)
                )

            def cursor(inner):
                return inner

            def copy(inner, sql):
                inner.sql.append(sql)
                return nullcontext(inner.writer)

        connection = StagingConnection()
        result = staging.stage(connection, self.root, "base", dry_run=False)
        self.assertTrue(result["staged"])
        self.assertFalse(result["activated"])
        self.assertTrue(
            any(
                "INSERT INTO native_catalog_documents" in sql
                and "SELECT %s,path,raw" in sql
                for sql in connection.sql
            )
        )
        self.assertTrue(
            any(
                "INSERT INTO native_catalog_records" in sql
                and "SELECT %s,path,collection" in sql
                for sql in connection.sql
            )
        )
        self.assertFalse(
            any("UPDATE native_catalog_active" in sql for sql in connection.sql)
        )
        self.assertTrue(connection.writer.rows)
