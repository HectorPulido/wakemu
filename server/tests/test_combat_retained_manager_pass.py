"""One retained view shares validated managers only after its pruning boundary."""
from dataclasses import asdict
import unittest
from unittest.mock import patch

import test_combat_fake_fighter_area as area_fixture
from wakfu_server.combat_fake_fighter import verified_fake_fighter
from wakfu_server.combat_retained_effects import RetainedEffect
from wakfu_server.combat_retained_runtime import NativeRetainedRuntime
from wakfu_server.combat_state_ledger import StateLedger
from wakfu_server.combat_stat_effects import owned_effect_payload


class RetainedManagerPassTests(unittest.TestCase):
    def fixture(self, count=20):
        source = area_fixture.NativeFakeFighterAreaTests()
        fight, handler, _, packets = source.create()
        fight.actors[7].state_ledger = StateLedger(7)
        self.assertTrue(source.invoke(handler))
        fight.native_retained_tracking = True
        fight.native_retained_order = []
        fight.native_retained_records = {}
        fight.native_owned_group_effects = {}
        fight.owned_stat_effects = {}
        fight.state_wire_payloads = {}
        for uid in range(100, 100 + count):
            payload = owned_effect_payload(
                uid=uid,
                base_uid=None,
                generic_effect=308265,
                caster_id=7,
                target_id=901,
                value=0,
            )
            fight.owned_stat_effects[uid] = dict(
                payload=payload.hex(), target_id=901, effect_class=400
            )
            fight.native_retained_records[uid] = asdict(
                RetainedEffect(uid, 901, 400, 308265, manager_id=901)
            )
            fight.native_retained_order.append(uid)
        runtime = NativeRetainedRuntime(
            fight,
            packets,
            plan=dict(native_retained_container=dict(present=False)),
            state_catalog={},
            action_id=1,
            timing=None,
            metadata={},
        )
        return runtime, fight

    def test_twenty_actual_faw_targets_require_two_validations_per_view(self):
        runtime, fight = self.fixture()
        with patch(
            "wakfu_server.combat_fake_fighter.verified_fake_fighter",
            wraps=verified_fake_fighter,
        ) as verify:
            first = runtime.view()
            self.assertEqual(verify.call_count, 2)
            second = runtime.view()
            self.assertEqual(verify.call_count, 4)
        self.assertEqual([entry.uid for entry in first.entries], list(range(100, 120)))
        self.assertEqual(first.entries, second.entries)
        self.assertFalse(any("manager_pass" in key for key in vars(first)))
        self.assertFalse(any("manager_pass" in key for key in vars(runtime)))

    def test_next_view_rechecks_changed_actual_constructor_authority(self):
        runtime, fight = self.fixture()
        before = runtime.view()
        fight.native_effect_areas[901]["native_faw_constructor"] = {}
        with self.assertRaisesRegex(ValueError, "faW constructor snapshot"):
            runtime.view()
        self.assertEqual(len(before.entries), 20)

    def test_pruned_retired_manager_is_not_reused_in_post_prune_pass(self):
        runtime, fight = self.fixture(count=0)
        row = fight.native_effect_areas.pop(901)
        fight.native_retired_area_managers = {901: row}
        with patch(
            "wakfu_server.combat_fake_fighter.verified_fake_fighter",
            wraps=verified_fake_fighter,
        ) as verify:
            view = runtime.view()
        self.assertEqual(verify.call_count, 1)  # Before prune only.
        self.assertEqual(fight.native_retired_area_managers, {})
        self.assertEqual(view.entries, ())

    def test_unenumerated_selected_area_keeps_actual_manager_fallback_guard(self):
        runtime, fight = self.fixture()
        del fight.native_effect_areas[901]["state_ledger"]
        with self.assertRaisesRegex(ValueError, "registered area state manager"):
            runtime.view()


if __name__ == "__main__":
    unittest.main()
