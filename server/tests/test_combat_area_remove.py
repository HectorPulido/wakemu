import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_area_remove import (
    select_removal_area,
    NativeAreaRemovalHandler,
)
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class AreaRemovalTests(unittest.TestCase):
    def fixture(self):
        rows = {
            uid: dict(
                uid=uid,
                reference=ref,
                cell=(0, 0, 0),
                native_cells_xy=((0, 0),),
                owner_id=7,
                direction=7,
                native_area_contract="faY",
                child_effect_uids={},
            )
            for uid, ref in ((901, 1474), (902, 1477))
        }
        fight = SimpleNamespace(
            id=11,
            actors={7: SimpleNamespace(team=0)},
            native_effect_areas=rows,
            native_retained_records={},
        )
        return fight

    def test_explicit_area_mismatch_and_unique_coordinate_selection(self):
        fight = self.fixture()
        self.assertIsNone(select_removal_area(fight, 1477, 901, (0, 0, 0)))
        self.assertEqual(select_removal_area(fight, 1477, None, (0, 0, 0))["uid"], 902)
        with self.assertRaisesRegex(ValueError, "collection producer"):
            select_removal_area(fight, -1, None, (0, 0, 0))
        self.assertEqual(select_removal_area(fight, -1, 901, (0, 0, 0))["uid"], 901)

    def test_real_843_packet_and_exact_area_callback_after_unregister(self):
        fight = self.fixture()
        packets = []
        seen = []
        handler = NativeAreaRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            context=lambda *a: StatExecutionContext(True, True, None, False, b""),
            container=lambda *a: ({"container_type": None}, None),
            rng=lambda: 0.5,
        )
        handler.events = SimpleNamespace(
            removed=lambda row: seen.append(
                (row["uid"], row["uid"] in fight.native_effect_areas)
            )
        )
        invocation = EffectInvocation(300001, 1, 7, 901, (0, 0, 0))
        with patch(
            "wakfu_server.combat_area_remove.native_effect_areas",
            return_value={"1474": {"raw_bdi": True}},
        ):
            self.assertTrue(
                handler({"effect_class": 843}, {"parameters": [-1]}, invocation)
            )
        self.assertEqual(seen, [(901, False)])
        self.assertEqual(set(fight.native_effect_areas), {902})
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(packets[0][1][12], 1)

    def test_911_cell_route_uses_same_native_removal_and_complete_area_order(self):
        from wakfu_server.combat_global_pv_collections import (
            initialize_global_pv_collections,
            register_global_area,
            global_area_order,
        )

        fight = self.fixture()
        areas = fight.native_effect_areas
        fight.native_effect_areas = {}
        initialize_global_pv_collections(fight, (7,))
        for uid, row in areas.items():
            fight.native_effect_areas[uid] = row
            register_global_area(fight, uid)
        expected = global_area_order(fight)[0]
        self.assertEqual(
            select_removal_area(fight, -1, None, (0, 0, 0))["uid"], expected
        )
        packets, phases = [], []
        handler = NativeAreaRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            rng=lambda: 0.5,
            context=lambda *args: StatExecutionContext(True, True, None, False, b""),
            container=lambda *args: ({"container_type": None}, None),
        )
        handler.events = SimpleNamespace(removed=lambda row: None)
        from wakfu_server.combat_state_managers import retained_area_pv_row

        def phase(effect, invocation, **data):
            phases.append((data["channel"], data["value"]))
            if data["channel"] in (3, 4):
                self.assertNotIn(invocation.target_id, fight.native_effect_areas)
                self.assertIs(
                    retained_area_pv_row(fight, invocation.target_id), areas[expected]
                )

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        effect = {"effect_class": 911, "target_masks": [None] * 7}
        invocation = EffectInvocation(300001, 1, 7, None, (0, 0, 0))
        with patch(
            "wakfu_server.combat_area_remove.native_effect_areas",
            return_value={
                str(row["reference"]): {"raw_bdi": True} for row in areas.values()
            },
        ):
            invocation = handler.prepare(effect, {"parameters": [-1]}, invocation)
            self.assertTrue(handler(effect, {"parameters": [-1]}, invocation))
        self.assertEqual(packets[0][0], 12613)
        self.assertEqual(packets[0][1][12], 1)
        self.assertNotIn(expected, fight.native_effect_areas)
        self.assertNotIn(expected, global_area_order(fight))
        self.assertEqual(phases, [(1, 0), (2, 0), (3, 0), (4, 0)])
        self.assertFalse(handler.prepared)
        self.assertIsNone(retained_area_pv_row(fight, expected))

    def test_843_null_recipient_is_explicitly_allowed_before_coordinate_selection(self):
        fight = self.fixture()
        calls = []
        handler = NativeAreaRemovalHandler(
            fight,
            [],
            action_id=2,
            allocate_uid=lambda: 999,
            rng=lambda: 0.5,
            context=lambda *args: None,
            container=lambda *args: None,
        )

        def phase(effect, invocation, **data):
            if invocation.target_id is None:
                self.assertIs(data.get("_nullable_target"), True)
            calls.append((data["channel"], invocation.target_id))

        handler.event_lifecycle = SimpleNamespace(phase=phase)
        invocation = EffectInvocation(385223, 10, 7, None, (0, 0, 0))
        handler.prepare(
            {"effect_class": 843, "target_masks": [None] * 7}, {}, invocation
        )
        self.assertEqual(calls, [(1, None)])

    def test_removed_area_scope_exception_does_not_leak_pv(self):
        from wakfu_server.combat_state_managers import (
            removed_area_pv_scope,
            retained_area_pv_row,
        )

        fight = self.fixture()
        row = fight.native_effect_areas.pop(901)
        with self.assertRaisesRegex(RuntimeError, "reaction rejected"):
            with removed_area_pv_scope(fight, row):
                self.assertIs(retained_area_pv_row(fight, 901), row)
                raise RuntimeError("reaction rejected")
        self.assertIsNone(retained_area_pv_row(fight, 901))
        self.assertNotIn(901, fight.native_effect_areas)

    def test_bcF_false_suppresses_packet_and_removal(self):
        fight = self.fixture()
        packets = []
        handler = NativeAreaRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            context=lambda *a: StatExecutionContext(True, True, None, False, b""),
            container=lambda *a: None,
            rng=lambda: 0.5,
        )
        with patch(
            "wakfu_server.combat_area_remove.native_effect_areas",
            return_value={"1474": {"raw_bdi": False}},
        ):
            self.assertFalse(
                handler(
                    {"effect_class": 843},
                    {"parameters": [-1]},
                    EffectInvocation(300001, 1, 7, 901, (0, 0, 0)),
                )
            )
        self.assertEqual(packets, [])
        self.assertIn(901, fight.native_effect_areas)
