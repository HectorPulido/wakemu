"""A changed item document does not recompile the native combat variants."""
import copy
import tempfile
from pathlib import Path
from unittest.mock import patch

from postgres_case import PostgresCase
from tools import publish_compiled_combat_catalog as publisher
from tools import reuse_compiled_variants as reuse
from wakfu_server.native_compiled_catalog import canonical_bytes


class VariantReusePostgresTests(PostgresCase):
    def test_item_change_reuses_all_combat_variants_with_full_manifest_parity(self):
        revision = "a" * 64
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_catalog_releases "
                "(revision,document_count,source_bytes,complete) VALUES(%s,0,0,true)",
                (revision,),
            )
        initial = dict(
            policy="variant-reuse-test",
            source_revision=revision,
            source_inventory_sha256="b" * 64,
            compiler_contract_sha256="c" * 64,
            config_sha256="d" * 64,
            config={},
            compiler_sources={},
            source_documents={
                "item-exchange-metadata.json": "1" * 64,
                "spell-effect-trees.json": "2" * 64,
            },
        )
        changed = copy.deepcopy(initial)
        changed["source_inventory_sha256"] = "e" * 64
        changed["source_documents"]["item-exchange-metadata.json"] = "3" * 64
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)

        def spool(name):
            value = publisher.PublicationSpool(str(Path(temporary.name) / name))
            self.addCleanup(value.db.close)
            return value

        def variants(target):
            target.collection("shared.states", {"1": {"level": 1}})
            target.collection("shared.state_effects", {"2": {"damage": 3}})
            result = {}
            for name in ("player", "npc_imported", "npc_baseline", "weapon"):
                source, effects, entry = (
                    name + ".source_effects",
                    name + ".effects",
                    name + ".entry_effects",
                )
                target.collection(source, {"2": {"damage": 3}})
                target.collection(
                    effects, {"2": {"damage": 3}}, representation="frozen_effect"
                )
                target.collection(entry, {"2": True})
                result[name] = dict(
                    source_effects=source, effects=effects, entry_effects=entry
                )
            return dict(
                variants=result,
                original_output_index={name: [] for name in result},
                states="shared.states",
                state_effects="shared.state_effects",
            )

        old = spool("old.sqlite")
        old_variants = variants(old)
        old_item = old.document(
            "item-exchange-metadata.json", {"items": {"1": {"price": 1}}}
        )
        old_manifest = dict(
            initial,
            **old_variants,
            raw_documents={"item-exchange-metadata.json": old_item},
            collections=old.collections
        )
        with self.store.connection() as db:
            old_generation = publisher.publish(db, old, old_manifest, canonical_bytes)

        incremental = spool("incremental.sqlite")
        with patch("wakfu_server.native_catalog._database", return_value=self.store):
            result = reuse.reuse(incremental, changed)
        self.assertEqual(result, old_variants)
        self.assertEqual(
            incremental.db.execute("SELECT count(*) FROM records").fetchone()[0], 0
        )
        new_item = incremental.document(
            "item-exchange-metadata.json", {"items": {"1": {"price": 2}}}
        )
        actual = dict(
            changed,
            **result,
            raw_documents={"item-exchange-metadata.json": new_item},
            collections=incremental.collections
        )

        full = spool("full.sqlite")
        full_variants = variants(full)
        full_item = full.document(
            "item-exchange-metadata.json", {"items": {"1": {"price": 2}}}
        )
        expected = dict(
            changed,
            **full_variants,
            raw_documents={"item-exchange-metadata.json": full_item},
            collections=full.collections
        )
        self.assertEqual(canonical_bytes(actual), canonical_bytes(expected))
        with self.store.connection() as db:
            new_generation = publisher.publish(db, incremental, actual, canonical_bytes)
            rows = db.execute(
                "SELECT generation,collection,content_id FROM native_compiled_catalog_collections "
                "WHERE generation=ANY(%s)",
                ([old_generation, new_generation],),
            ).fetchall()
        content = {
            (row["generation"], row["collection"]): row["content_id"] for row in rows
        }
        for name in old_variants["variants"]["player"].values():
            self.assertEqual(
                content[(old_generation, name)], content[(new_generation, name)]
            )
        self.assertNotEqual(
            content[(old_generation, "documents.item-exchange-metadata.json.items")],
            content[(new_generation, "documents.item-exchange-metadata.json.items")],
        )
