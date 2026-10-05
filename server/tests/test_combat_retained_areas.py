import unittest
from dataclasses import asdict
from types import SimpleNamespace
from wakfu_server.combat_effect_area_codec import area_payload
from wakfu_server.combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
    NativeRetainedRemoval,
    register_owned_removals,
)


class NativeRetainedAreaTests(unittest.TestCase):
    def fixture(self, keep):
        timing = bytes.fromhex(
            "08001a0f080010ffffffffffffffffff01180020ffffffffffffffffff01"
        )
        payload = area_payload(
            uid=902,
            base_uid=None,
            effect_reference=123,
            area_reference=1546,
            area_uid=901,
            level=1,
            keep_after=keep,
            direction=None,
            caster_id=7,
            cell=(2, -3, 4),
            timing_payload=timing,
        )
        row = dict(
            uid=902,
            area_uid=901,
            target_id=None,
            caster_id=7,
            state_uid=None,
            effect_class=315,
            payload=payload.hex(),
            keep_after=keep,
            executed=True,
        )
        record = RetainedEffect(
            902, None, 315, 123, manager_id=7, container_present=False
        )
        actor = SimpleNamespace(state_ledger=SimpleNamespace(entries=()))
        fight = SimpleNamespace(
            id=12,
            actors={7: actor},
            owned_stat_effects={},
            state_wire_payloads={},
            native_owned_group_effects={},
            native_owned_area_effects={902: row},
            native_effect_areas={
                901: dict(
                    uid=901, cell=(2, -3, 4), owner_id=7, native_hour_contract=True
                )
            },
        )
        return fight, record, payload

    def test_native_eYQ_bbR_keep_flag_preserves_or_removes_only_area(self):
        for keep in (False, True):
            fight, record, payload = self.fixture(keep)
            view = NativeRetainedEffectView(
                fight, [record], population_verified_complete=True
            )
            removal = NativeRetainedRemoval(view)
            packets = []
            register_owned_removals(
                removal,
                stat_handler=SimpleNamespace(fight=fight),
                packets=packets,
                action_id=3,
            )
            removal.remove([902])
            self.assertEqual(fight.native_owned_area_effects, {})
            self.assertEqual(bool(fight.native_effect_areas), keep)
            self.assertEqual(packets[0][0], 13560)
            self.assertEqual(packets[0][1][18:-16], payload)

    def test_missing_caster_manager_rejects_before_mutation(self):
        fight, record, payload = self.fixture(False)
        forged = RetainedEffect(
            902, None, 315, 123, manager_id=8, container_present=False
        )
        with self.assertRaises(ValueError):
            NativeRetainedEffectView(fight, [forged], population_verified_complete=True)
        self.assertIn(901, fight.native_effect_areas)
