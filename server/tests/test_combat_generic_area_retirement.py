"""Generic Qs retirement is published once for selected areas only."""
import struct
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_effect_area_events import NativeAreaEventRuntime
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_stat_handler import StatExecutionContext


class GenericAreaRetirementTests(unittest.TestCase):
    def _remove(self, *, reference=411, rail=False):
        from wakfu_server.combat_area_remove import NativeAreaRemovalHandler
        from wakfu_server.combat_effect_area_codec import area_retirement
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            register_global_area,
        )

        rows = {
            uid: dict(
                uid=uid,
                reference=ref,
                cell=(0, 0, 0),
                native_cells_xy=((0, 0),),
                owner_id=7,
                direction=0,
                native_area_contract="faY",
                child_effect_uids={},
            )
            for uid, ref in ((901, reference), (902, 1477))
        }
        if rail:
            from wakfu_server.combat_microbot_rails import SOURCE

            rows[901]["native_microbot_rail_source"] = SOURCE
        fight = SimpleNamespace(
            id=11,
            actors={7: SimpleNamespace(id=7, team=0)},
            native_effect_areas={},
            native_retained_records={},
            native_retired_area_managers={},
        )
        initialize_global_pv_collections(fight, (7,))
        fight.native_effect_areas.update(rows)
        for uid in rows:
            register_global_area(fight, uid)

        definitions = {
            str(ref): dict(
                type="GLYPH",
                properties=[],
                native_area_properties=[],
                entry_masks=[],
                exit_masks=[],
            )
            for ref in (reference, 1477)
        }
        packets = []
        dispatcher = SimpleNamespace(effects={})
        events = NativeAreaEventRuntime(fight, dispatcher, definitions=definitions)
        events.area_removed = lambda area_uid: packets.append(
            area_retirement(fight.id, 2, area_uid)
        )
        rail_calls = []
        events.microbot_rail_removed = lambda area_uid: rail_calls.append(area_uid)

        handler = NativeAreaRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            context=lambda *args: StatExecutionContext(True, True, None, False, b""),
            container=lambda *args: ({"container_type": None}, None),
            rng=lambda: 0.5,
        )
        handler.events = events
        effect = {"effect_class": 911, "target_masks": [None] * 7}
        invocation = EffectInvocation(300001, 1, 7, 901, (0, 0, 0))
        with patch(
            "wakfu_server.combat_area_remove.native_effect_areas",
            return_value={
                str(reference): {"raw_bdi": True},
                "1477": {"raw_bdi": True},
            },
        ):
            invocation = handler.prepare(effect, {"parameters": [-1]}, invocation)
            self.assertTrue(handler(effect, {"parameters": [-1]}, invocation))
        return fight, packets, rail_calls

    def test_911_cocoon_area_retirement_publishes_once_and_keeps_foreign_area(self):
        fight, packets, _ = self._remove(reference=411)
        retirements = [(op, body) for op, body in packets if op == 13726]
        self.assertEqual(len(retirements), 1)
        self.assertEqual(struct.unpack(">iiiq", retirements[0][1]), (11, 2, -1, 901))
        self.assertEqual(set(fight.native_effect_areas), {902})
        self.assertEqual([opcode for opcode, _ in packets], [12613, 13726])

    def test_non_cocoon_area_uses_same_generic_retirement_delivery(self):
        fight, packets, _ = self._remove(reference=1474)
        self.assertEqual(
            [struct.unpack(">iiiq", body) for op, body in packets if op == 13726],
            [(11, 2, -1, 901)],
        )
        self.assertEqual(set(fight.native_effect_areas), {902})

    def test_rail_area_uses_generic_delivery_without_duplicate_legacy_callback(self):
        fight, packets, rail_calls = self._remove(reference=1474, rail=True)
        self.assertEqual(
            [struct.unpack(">iiiq", body) for op, body in packets if op == 13726],
            [(11, 2, -1, 901)],
        )
        self.assertEqual(rail_calls, [])
        self.assertEqual(set(fight.native_effect_areas), {902})


if __name__ == "__main__":
    unittest.main()
