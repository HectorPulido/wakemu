"""eYd909 delegates native target-Qq removal to inherited eYc."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_area_remove import NativeAreaRemovalHandler
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_effect_dispatch import EffectInvocation


class TargetAreaRemoval909Tests(unittest.TestCase):
    def fixture(self):
        from test_combat_area_remove import AreaRemovalTests

        fight = AreaRemovalTests().fixture()
        packets = []
        seen = []
        h = NativeAreaRemovalHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=lambda: 999,
            context=lambda *a: StatExecutionContext(True, True, None, False, b""),
            container=lambda *a: ({"container_type": None}, None),
            rng=lambda: 0.5,
        )
        h.events = SimpleNamespace(
            removed=lambda row: seen.append(
                (row["uid"], row["uid"] in fight.native_effect_areas)
            )
        )
        return fight, h, packets, seen

    def test909_explicit_registered_qq_uses_native_removal_packet_and_after_callback(
        self,
    ):
        fight, h, packets, seen = self.fixture()
        with patch(
            "wakfu_server.combat_area_remove.native_effect_areas",
            return_value={"1474": {"raw_bdi": True}},
        ):
            self.assertTrue(
                h(
                    {"effect_class": 909},
                    {"parameters": [-1]},
                    EffectInvocation(1, 1, 7, 901, (0, 0, 0)),
                )
            )
        self.assertEqual(seen, [(901, False)])
        self.assertEqual(set(fight.native_effect_areas), {902})
        self.assertEqual(packets[0][0], 13497)

    def test909_explicit_mismatch_does_not_fall_back_to_matching_neighbor(self):
        fight, h, packets, seen = self.fixture()
        self.assertFalse(
            h(
                {"effect_class": 909},
                {"parameters": [1477]},
                EffectInvocation(1, 1, 7, 901, (0, 0, 0)),
            )
        )
        self.assertEqual(set(fight.native_effect_areas), {901, 902})
        self.assertEqual(packets, [])
        self.assertEqual(seen, [])
