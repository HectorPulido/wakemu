"""Fast-path contracts for reusing compiled bytes after reviewed source edits."""

import copy
import hashlib
import unittest
from pathlib import Path

from tools import reuse_unchanged_compiled_catalog as reuse
from tools.publish_compiled_combat_catalog import ordered_bytes


def identity(*, changed_source=None, source_revision="a", config="c"):
    compiler_sources = {
        "wakfu_server/combat/combat_spell.py": "combat-v1",
        "wakfu_server/combat/combat_group_store.py": "runtime-v1",
        "wakfu_server/maps/monster_removal_ecology.py": "runtime-v1",
    }
    if changed_source:
        compiler_sources[changed_source] = "changed"
    documents = {"spell-effect-trees.json": "source-document-v1"}
    return {
        "policy": "policy-v1",
        "source_revision": source_revision,
        "source_inventory_sha256": "b" * 64,
        "compiler_contract_sha256": "d" * 64,
        "config_sha256": config * 64 if len(config) == 1 else config,
        "source_documents": documents,
        "compiler_sources": compiler_sources,
        "config": {"combat": config},
    }


class ReuseCompatibilityTests(unittest.TestCase):
    def test_reviewed_loader_override_is_exact_and_one_way(self):
        before, after = identity(), identity()
        path, (old, new) = next(iter(reuse.REVIEWED_LOADER_OVERRIDE.items()))
        before["compiler_sources"][path] = old
        after["compiler_sources"][path] = new
        self.assertTrue(reuse.compatible(before, after))
        self.assertFalse(reuse.compatible(after, before))
        future = copy.deepcopy(after)
        future["compiler_sources"][path] = "f" * 64
        self.assertFalse(reuse.compatible(before, future))
        extra = copy.deepcopy(after)
        extra["compiler_sources"]["wakfu_server/combat/combat_group_store.py"] = (
            "f" * 64
        )
        self.assertFalse(reuse.compatible(before, extra))
        extra = copy.deepcopy(after)
        extra["config"] = {"combat": "different"}
        self.assertFalse(reuse.compatible(before, extra))

    def test_variant_reuse_bundle_requires_every_exact_source_hash(self):
        before, after = identity(), identity()
        for path, (old, new) in reuse.REVIEWED_VARIANT_REUSE_BUNDLE.items():
            if old is None:
                before["compiler_sources"].pop(path, None)
            else:
                before["compiler_sources"][path] = old
            after["compiler_sources"][path] = new
        self.assertTrue(reuse.compatible(before, after))
        for path in reuse.REVIEWED_VARIANT_REUSE_BUNDLE:
            changed = copy.deepcopy(after)
            changed["compiler_sources"][path] = "f" * 64
            self.assertFalse(reuse.compatible(before, changed))
        after["compiler_sources"]["wakfu_server/combat/unreviewed.py"] = "f" * 64
        self.assertFalse(reuse.compatible(before, after))

    def test_reviewed_publisher_migration_is_exact_and_one_way(self):
        old_digest, new_digest = next(iter(reuse.REVIEWED_PUBLISHER_TRANSITIONS))
        previous, current = identity(), identity()
        previous["compiler_sources"][reuse.PUBLISHER_SOURCE] = old_digest
        current["compiler_sources"][reuse.PUBLISHER_SOURCE] = new_digest
        self.assertTrue(reuse.compatible(previous, current))
        self.assertFalse(reuse.compatible(current, previous))
        future = identity()
        future["compiler_sources"][reuse.PUBLISHER_SOURCE] = "future-edit"
        self.assertFalse(reuse.compatible(previous, future))
        self.assertFalse(reuse.compatible(current, future))
        other_change = identity(
            changed_source="wakfu_server/combat/combat_group_store.py"
        )
        other_change["compiler_sources"][reuse.PUBLISHER_SOURCE] = new_digest
        self.assertFalse(reuse.compatible(previous, other_change))
        changed_config = dict(current, config={"combat": "different"})
        self.assertFalse(reuse.compatible(previous, changed_config))

    def test_world_dispatch_modules_can_change_without_invalidating_catalog(self):
        for path in reuse.WORLD_DISPATCH_ONLY:
            with self.subTest(path=path):
                before = identity()
                before["compiler_sources"][path] = "old"
                after = identity()
                after["compiler_sources"][path] = "new"
                self.assertTrue(reuse.compatible(before, after))

    def test_world_dispatch_modules_have_no_package_or_publisher_references(self):
        # These are standalone World dispatch entry points.  If a compiler
        # dependency starts referring to one, review its reuse classification.
        server = Path(__file__).resolve().parents[1]
        package = server / "wakfu_server"
        modules = {Path(path).stem: server / path for path in reuse.WORLD_DISPATCH_ONLY}
        self.assertEqual(len(modules), len(reuse.WORLD_DISPATCH_ONLY))
        for path in [
            *package.rglob("*.py"),
            server / "tools/publish_compiled_combat_catalog.py",
        ]:
            source = path.read_text(encoding="utf-8")
            for name, owner in modules.items():
                if path != owner:
                    self.assertNotIn(name, source, f"{path} references {name}")

    def test_only_explicit_runtime_sources_are_compatible(self):
        previous = identity()
        current = identity(changed_source="wakfu_server/combat/combat_group_store.py")
        self.assertTrue(reuse.compatible(previous, current))

    def test_relevant_source_inventory_config_and_revision_changes_are_denied(self):
        previous = identity()
        cases = (
            identity(changed_source="wakfu_server/combat/combat_spell.py"),
            identity(source_revision="e"),
            identity(config="f"),
        )
        changed_inventory = identity()
        changed_inventory["source_inventory_sha256"] = "f" * 64
        cases += (changed_inventory,)
        for current in cases:
            with self.subTest(current=current):
                self.assertFalse(reuse.compatible(previous, current))

    def test_empty_or_unrecognized_compiler_diff_is_not_a_reuse_candidate(self):
        unchanged = identity()
        self.assertFalse(reuse.compatible(unchanged, unchanged.copy()))
        missing_source = identity()
        del missing_source["compiler_sources"]["wakfu_server/combat/combat_spell.py"]
        self.assertFalse(reuse.compatible(unchanged, missing_source))


class ReuseDatabaseTests(unittest.TestCase):
    def setUp(self):
        self.current = identity(
            changed_source="wakfu_server/combat/combat_group_store.py"
        )
        self.previous = identity()
        self.previous["compiler_contract_sha256"] = "c" * 64
        key_raw = ordered_bytes(["27"])
        key_hash = hashlib.sha256(key_raw).hexdigest()
        self.previous["collections"] = {
            "effects": {
                "kind": "dict",
                "count": 1,
                "ordered_keys_sha256": key_hash,
                "representation": "native_json",
                "records_sha256": "f" * 64,
            }
        }
        raw = ordered_bytes(self.previous)
        self.candidate = {
            "generation": hashlib.sha256(raw).hexdigest(),
            "manifest_raw": raw,
            "manifest": self.previous,
        }
        self.rows = [
            {
                "collection": "effects",
                "kind": "dict",
                "record_count": 1,
                "ordered_keys_raw": key_raw,
                "ordered_keys_sha256": key_hash,
                "content_id": 912,
                "content_complete": True,
                "content_collection": "effects",
                "content_kind": "dict",
                "content_count": 1,
                "content_representation": "native_json",
                "content_keys_sha256": key_hash,
                "content_records_sha256": "f" * 64,
            }
        ]
        self.events = []
        self.clone_args = None
        self.complete_args = None

    def fake_db(self, *, wrong_rows=False):
        rows = self.rows
        if wrong_rows:
            rows = [dict(rows[0], content_complete=False)]

        class DB:
            def execute(inner, query, params=None):
                self.events.append((query, params))
                if "WHERE policy=%s" in query and "AND complete" in query:
                    # First complete query is exact-identity lookup; second is candidates.
                    if "compiler_contract_sha256=%s" in query:
                        return Result(None)
                    return Result([self.candidate])
                if "pg_class" in query:
                    return Result({"relkind": "v"})
                if "native_compiled_catalog_collections c" in query:
                    return Result(rows)
                if query.startswith("INSERT INTO native_compiled_catalog_releases"):
                    self.clone_args = params
                if query.startswith("UPDATE native_compiled_catalog_releases"):
                    self.complete_args = params
                return Result(None)

        class Result:
            def __init__(inner, value):
                inner.value = value

            def fetchone(inner):
                return inner.value if isinstance(inner.value, dict) else None

            def fetchall(inner):
                return inner.value if isinstance(inner.value, list) else []

        return DB()

    def test_clones_manifest_and_content_references_without_spooling_records(self):
        generation = reuse.try_reuse(self.fake_db(), self.current, ordered_bytes)
        self.assertEqual(generation, hashlib.sha256(self.clone_args[-2]).hexdigest())
        self.assertIsNotNone(self.clone_args)
        self.assertEqual(self.complete_args, (generation,))
        clone = self.clone_args[-1].obj
        self.assertEqual(clone["compiler_sources"], self.current["compiler_sources"])
        self.assertEqual(clone["collections"], self.previous["collections"])
        queries = [query for query, _ in self.events]
        self.assertFalse(
            any("FROM native_compiled_catalog_records" in query for query in queries)
        )
        self.assertTrue(any("SELECT %s,collection" in query for query in queries))
        self.assertLess(
            next(
                i for i, q in enumerate(queries) if "pg_advisory_xact_lock_shared" in q
            ),
            next(
                i
                for i, q in enumerate(queries)
                if "native_compiled_catalog_releases" in q
            ),
        )

    def test_corrupt_or_incomplete_candidate_content_falls_back(self):
        db = self.fake_db(wrong_rows=True)
        self.assertIsNone(reuse.try_reuse(db, self.current, ordered_bytes))
        self.assertIsNone(self.clone_args)

    def test_relevant_compiler_source_and_config_changes_do_not_clone(self):
        for current in (
            identity(changed_source="wakfu_server/combat/combat_spell.py"),
            identity(
                changed_source="wakfu_server/combat/combat_group_store.py",
                config="f",
            ),
        ):
            with self.subTest(current=current):
                self.assertIsNone(
                    reuse.try_reuse(self.fake_db(), current, ordered_bytes)
                )
                self.assertIsNone(self.clone_args)

    def test_legacy_non_view_storage_falls_back_without_copying_records(self):
        db = self.fake_db()
        original = db.execute

        def legacy(query, params=None):
            if "pg_class" in query:
                self.events.append((query, params))
                return type(
                    "Result", (), {"fetchone": lambda _self: {"relkind": "r"}}
                )()
            return original(query, params)

        db.execute = legacy
        self.assertIsNone(reuse.try_reuse(db, self.current, ordered_bytes))
        self.assertIsNone(self.clone_args)


if __name__ == "__main__":
    unittest.main()
