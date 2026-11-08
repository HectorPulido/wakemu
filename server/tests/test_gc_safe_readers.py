"""Native GC demand traversal requires callback-free preflight/serialization."""
from contextlib import nullcontext
from copy import deepcopy
import unittest
from unittest.mock import patch
from test_gc_owned_collections import OwnedCollectionGCTests
from wakfu_server import combat_retained_gc_boundary as boundary
from wakfu_server.combat_geometry_snapshot import ImmutableTerrainSet
from wakfu_server.combat_source_parent_index import OwnedStateSourceRow
from wakfu_server.combat_static_catalogs import ImmutableCatalog


class SafeDemandReaderTests(unittest.TestCase):
    def test_native_equipment_and_custom_items_get_length_preserve_safe_reachability(
        self,
    ):
        from wakfu_server.combat_owned_equipment_pin import _digest

        previous, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
        payload = dict(
            version=1,
            actor_id=7,
            owner_id=7,
            sources={
                "equipment": [
                    {"reference": 6266, "effects": [350552], "metadata": {"level": 100}}
                ]
            },
            deferred={"conditions": [{"criteria": "1 == 1"}]},
            execution_sha256="0" * 64,
        )
        record = dict(payload, sha256=_digest(payload))
        original = deepcopy(record)
        catalog = ImmutableCatalog(record)
        fight.native_owned_equipment_sources = {"7": catalog}
        schemas, readers = [], set()
        self.assertTrue(
            boundary._canonical_graph(
                fight, reference_schemas=schemas, projection_opaque=readers
            )
        )
        self.assertEqual(schemas, [True])
        self.assertNotIn(None, readers)
        boundary.prepare_retired_gc(previous, fight, runtime, ())
        self.assertNotIn(uid, fight.native_retained_records)
        self.assertIn(dead, fight.actors)
        self.assertEqual(record, original)
        self.assertIs(catalog._source, record)
        self.assertEqual(catalog._views, {})
        for mode in ("metadata_items", "source_get", "set_length"):
            with self.subTest(mode=mode):
                previous, fight, runtime, dead, uid = OwnedCollectionGCTests().fixture()
                actor = fight.actors[dead]
                actor.native_context_hex = ""
                calls = []
                gate = nullcontext()
                if mode == "metadata_items":
                    row = fight.native_retained_records[uid]

                    def items():
                        calls.append("items")
                        actor.native_context_hex = "ff"
                        return dict.items(row)

                    row.items = items
                elif mode == "source_get":
                    source = OwnedStateSourceRow(fight.native_owned_group_effects[uid])
                    fight.native_owned_group_effects[uid] = source

                    def get(row, key, *default):
                        if row is source and key == "state_uid":
                            calls.append("get")
                            actor.native_context_hex = "ff"
                        return dict.get(row, key, *default)

                    gate = patch.object(OwnedStateSourceRow, "get", get)
                else:
                    # Fight fields serialize before actors, so the callback
                    # cannot change actor dictionary size during its iteration.
                    fight.terrain_alias = ImmutableTerrainSet(((4, 5, 0),))

                    def length(value):
                        calls.append("length")
                        actor.native_context_hex = "ff"
                        return frozenset.__len__(value)

                    gate = patch.object(ImmutableTerrainSet, "__len__", length)
                with gate:
                    schemas, readers = [], set()
                    self.assertTrue(
                        boundary._canonical_graph(
                            fight, reference_schemas=schemas, projection_opaque=readers
                        )
                    )
                    self.assertEqual(schemas, [True])
                    self.assertIn(None, readers)
                    self.assertEqual(calls, [])
                    boundary.prepare_retired_gc(previous, fight, runtime, ())
                    self.assertTrue(calls)
                    self.assertEqual(actor.native_context_hex, "ff")
                    self.assertIn(uid, fight.native_retained_records)
                    self.assertIn(uid, fight.native_owned_group_effects)


if __name__ == "__main__":
    unittest.main()
