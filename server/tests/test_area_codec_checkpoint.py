"""Area owner graph restore and checkpoint snapshots preserve payload aliases."""
import json
import unittest

from wakfu_server.combat_area_membership import OwnedAreaRow
from wakfu_server.combat_retained_collections import RetainedCollections, OwnedMap
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_state import Fight
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.checkpoint_worker import _checkpoint_fields


class AreaCodecCheckpointTests(unittest.TestCase):
    def fight(self, row):
        owner = RetainedCollections()
        fight = object.__new__(Fight)
        fight.__dict__.update(
            id=7,
            actors=owner.actors,
            native_retained_tracking=True,
            native_retained_records=owner.records,
            native_retained_order=owner.order,
            **owner.sources,
            **owner.area_sources
        )
        fight.native_effect_areas[11] = row
        fight.native_retired_area_managers[11] = row
        fight.area_alias = row
        fight.area_map_alias = fight.native_effect_areas
        return fight

    def test_tagged_rows_restore_same_graph_and_rebuild_observers(self):
        row = OwnedAreaRow(uid=11, state_ledger=StateLedger(11))
        before = self.fight(row)
        payload = encode_state(before)
        after = decode_state(json.loads(json.dumps(payload)))
        self.assertIs(type(after.area_alias), OwnedAreaRow)
        self.assertIs(after.area_alias, after.native_effect_areas[11])
        self.assertIs(after.area_alias, after.native_retired_area_managers[11])
        self.assertIs(after.area_map_alias, after.native_effect_areas)
        owner = after.native_retained_records.owner
        self.assertIs(owner.area_sources["native_effect_areas"], after.area_map_alias)
        self.assertTrue(
            all(item[0]() is owner for item in after.area_alias._membership_owners)
        )
        self.assertEqual(2, len(after.area_alias._membership_owners))
        self.assertIsNot(after.area_alias["state_ledger"], row["state_ledger"])

    def test_legacy_proven_rows_upgrade_and_opaque_rows_keep_fallback(self):
        before = self.fight(dict(uid=11, state_ledger=StateLedger(11)))
        before.native_effect_areas[22] = dict(uid=99)
        before.opaque_alias = before.native_effect_areas[22]
        payload = encode_state(before)
        for node in payload["nodes"]:
            if node.get("native_retained_storage") in (
                "native_effect_areas",
                "native_retired_area_managers",
            ):
                node.pop("native_retained_storage")
                node.pop("native_retained_owner", None)
        after = decode_state(payload)
        self.assertIs(type(after.native_effect_areas), OwnedMap)
        self.assertIs(type(after.area_alias), OwnedAreaRow)
        self.assertIs(type(after.opaque_alias), dict)
        self.assertIs(after.opaque_alias, after.native_effect_areas[22])
        self.assertIs(after.area_alias, after.native_effect_areas[11])
        self.assertIs(after.area_alias, after.native_retired_area_managers[11])

    def test_checkpoint_flattens_exact_area_rows_without_observers(self):
        row = OwnedAreaRow(uid=11, cells=[1, 2])
        before = self.fight(row)
        detached = _checkpoint_fields(
            dict(
                areas=before.native_effect_areas,
                retired=before.native_retired_area_managers,
                alias=row,
            )
        )
        self.assertIs(type(detached["areas"]), dict)
        self.assertIs(type(detached["alias"]), dict)
        self.assertIs(detached["alias"], detached["areas"][11])
        self.assertIs(detached["alias"], detached["retired"][11])
        self.assertEqual(dict(uid=11, cells=[1, 2]), detached["alias"])
        row["cells"].append(3)
        self.assertEqual([1, 2], detached["alias"]["cells"])
        json.dumps(detached, allow_nan=False)
