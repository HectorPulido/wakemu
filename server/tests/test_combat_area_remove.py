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
        with self.assertRaisesRegex(ValueError, "iteration order"):
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
        self.assertEqual(packets[0][0], 13497)

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
