import unittest
from dataclasses import asdict
from types import SimpleNamespace
from wakfu_server.combat_retained_runtime import (
    group_payload,
    native_retained_condition_effects,
    remove_owned_group,
)
from wakfu_server.combat_retained_effects import (
    RetainedEffect,
    NativeRetainedEffectView,
)
from wakfu_server.combat_effect_removal import _identity_fields, running_effect_removal


class RetainedCellGroupTests(unittest.TestCase):
    def fixture(self):
        timing = bytes.fromhex(
            "080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800"
        )
        payload = group_payload(
            uid=901,
            base_uid=800,
            generic_effect=350552,
            caster_id=7,
            target_id=None,
            cell=(4, 5, 0),
            container_type=None,
            container_id=None,
            timing_payload=timing,
        )
        row = dict(
            target_id=None, effect_class=949, state_uid=None, payload=payload.hex()
        )
        record = RetainedEffect(
            901, None, 949, 350552, manager_id=7, container_present=False
        )
        actor = SimpleNamespace(id=7, state_ledger=SimpleNamespace(entries=()))
        fight = SimpleNamespace(
            id=12,
            actors={7: actor},
            owned_stat_effects={},
            state_wire_payloads={},
            native_owned_group_effects={901: row},
            native_retained_records={901: asdict(record)},
            native_retained_order=[901],
            native_retained_tracking=True,
        )
        return fight, payload

    def test_real_exl_codec_has_cell_and_no_actor_target(self):
        fight, payload = self.fixture()
        expected = bytes.fromhex(
            "08850710a00618d8b21520002a0608041005180030075a2b080010ffffffffffffffffff011a0f080010ffffffffffffffffff01180020ffffffffffffffffff012800"
        )
        self.assertEqual(payload, expected)
        self.assertNotIn(7, _identity_fields(payload))
        self.assertEqual(
            native_retained_condition_effects(fight, 7), ((350552, 949, 901),)
        )
        packets = []
        remove_owned_group(fight, packets, action_id=3, uid=901)
        self.assertEqual(packets[0][0], 13560)
        self.assertEqual(fight.native_owned_group_effects, {})
        self.assertEqual(fight.native_retained_records, {})

    def test_absent_actor_does_not_allow_forged_manager_or_stat_owner(self):
        fight, payload = self.fixture()
        fight.native_retained_records[901]["manager_id"] = 999
        with self.assertRaises(ValueError):
            native_retained_condition_effects(fight, 7)
        for family in (193, 421):
            with self.assertRaises(ValueError):
                running_effect_removal(
                    12,
                    3,
                    effect_class=family,
                    target_id=7,
                    uid=901,
                    running_effect_payload=payload,
                )
        with self.assertRaises(ValueError):
            running_effect_removal(
                12,
                3,
                effect_class=949,
                target_id=999,
                uid=901,
                running_effect_payload=payload,
            )
