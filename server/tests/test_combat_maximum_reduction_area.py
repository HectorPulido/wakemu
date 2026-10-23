"""Actual native faW constructors preserve eWO's absent-PA muted execution."""
from copy import deepcopy
from dataclasses import asdict, replace
import unittest

import test_combat_fake_fighter_area as area_fixture
import test_combat_maximum_resource as resource_fixture
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.combat_event_replay import NativeEventSource
from wakfu_server.combat_fake_fighter import verified_fake_fighter
from wakfu_server.combat_maximum_resource import (
    NativeMaximumReductionHandler,
    remove_maximum_reduction,
)
from wakfu_server.combat_runner_callbacks import runner_value_scope
from wakfu_server.combat_stat_handler import StatExecutionContext
from wakfu_server.combat_state_timing import StateTimer


class MaximumReductionAreaTests(unittest.TestCase):
    def snapshot(self, row):
        copied = {key: value for key, value in row.items() if key != "state_ledger"}
        ledger = row.get("state_ledger")
        copied["state_ledger"] = (
            None if ledger is None else (ledger.actor_id, tuple(ledger.entries))
        )
        return deepcopy(copied)

    def create(self, reference=1688, retained=True):
        (
            fight,
            creator,
            allocated,
            packets,
        ) = area_fixture.NativeFakeFighterAreaTests().create()
        creator.fake_fighter_hp_enabled = True
        self.assertTrue(
            creator(
                {"effect_class": 339},
                {"parameters": [reference, 200]},
                EffectInvocation(323843, 200, 7, None, (2, 3, 0)),
            )
        )
        fight.phase = "active"
        fight.owned_stat_effects = {}
        packets.clear()
        context = StatExecutionContext(
            True, True, None, retained, b"", StateTimer(7, 2, "end")
        )
        handler = NativeMaximumReductionHandler(
            fight,
            packets,
            action_id=2,
            allocate_uid=creator.allocate_uid,
            context=lambda *args: context,
        )
        return fight, handler, allocated, packets

    def test_real_growl_and_other_faw_skip_absent_ap_mp_wp_without_inventing_pa(self):
        for reference in (1688, 566):
            for family in (56, 57, 192):
                with self.subTest(reference=reference, family=family):
                    fight, handler, allocated, packets = self.create(reference)
                    row = fight.native_effect_areas[901]
                    definition = native_effect_areas()[str(reference)]
                    self.assertEqual(
                        verified_fake_fighter(row, definition)["characteristic_ids"],
                        (1,),
                    )
                    before = self.snapshot(row)
                    invocation = EffectInvocation(319412, 200, 7, 901, (2, 3, 0))
                    self.assertTrue(
                        handler(
                            {"effect_class": family, "parameters": [6.0, 0.0]},
                            {},
                            invocation,
                        )
                    )
                    self.assertEqual(self.snapshot(row), before)
                    self.assertNotIn(901, fight.actors)
                    self.assertEqual(
                        packets, []
                    )  # Native mu(true) suppresses PR.b only.
                    uid = next(iter(fight.owned_stat_effects))
                    entry = fight.owned_stat_effects[uid]
                    self.assertTrue(entry["native_absent_characteristic"])
                    self.assertEqual(entry["actual"], 6)
                    remove_maximum_reduction(handler, uid)
                    self.assertEqual(self.snapshot(row), before)
                    self.assertFalse(fight.owned_stat_effects)
                    self.assertEqual([opcode for opcode, _ in packets], [13560])

    def test_instant_muted_execution_keeps_absent_source_literals_and_real_observer(
        self,
    ):
        fight, handler, _, packets = self.create(retained=False)
        seen = []
        invocation = EffectInvocation(319412, 200, 7, 901, (2, 3, 0))
        for amount in (-2, -1):
            with runner_value_scope(
                lambda source, value: seen.append(value)
            ) as observer:
                current = replace(invocation, native_value_scope=observer)
                self.assertTrue(
                    handler(
                        {"effect_class": 57, "parameters": [float(amount), 0.0]},
                        {},
                        current,
                    )
                )
        self.assertEqual(seen, [-2, -1])
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

    def test_actual_trigger_descriptor_resolves_minus_one_before_absent_pa_application(
        self,
    ):
        fight, handler, _, packets = self.create(retained=False)
        source = NativeEventSource(
            uid=950,
            generic_effect=100,
            value=5,
            caster_id=7,
            target_id=7,
            cell=(0, 0, 0),
            event_ids=(),
            channel=3,
            manager_actor_id=7,
            source_parent_uid=None,
            suppresses_level_one=False,
            suppresses_all=False,
            suppressed=False,
            native_events_verified=True,
            effect_action_id=57,
        )
        source.validate()
        seen = []
        with runner_value_scope(lambda source, value: seen.append(value)) as observer:
            invocation = EffectInvocation(
                319412,
                200,
                7,
                901,
                (2, 3, 0),
                native_trigger_context=asdict(source),
                native_value_scope=observer,
            )
            self.assertTrue(
                handler({"effect_class": 57, "parameters": [-1.0, 0.0]}, {}, invocation)
            )
        self.assertEqual(seen, [5])
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

    def test_missing_or_corrupt_pv_authority_is_not_muted(self):
        fight, handler, allocated, packets = self.create()
        initial_uids = list(allocated)
        definition = {"effect_class": 57, "parameters": [6.0, 0.0]}
        with self.assertRaisesRegex(ValueError, "target PV"):
            handler(definition, {}, EffectInvocation(319412, 200, 7, 999, (2, 3, 0)))
        fight.native_effect_areas[901]["native_faw_constructor"][
            "characteristic_ids"
        ] = (1, 3)
        with self.assertRaises(ValueError):
            handler(definition, {}, EffectInvocation(319412, 200, 7, 901, (2, 3, 0)))
        self.assertEqual(allocated, initial_uids)
        self.assertEqual((fight.owned_stat_effects, packets), ({}, []))

    def test_fighter_missing_snapshot_still_fails_instead_of_gaining_area_defaults(
        self,
    ):
        fixture = resource_fixture.MaximumResourceTests()
        fixture.setUp()
        del fixture.actor.effect_stats[3]
        handler = NativeMaximumReductionHandler(
            fixture.fight,
            fixture.packets,
            action_id=1,
            allocate_uid=fixture.handler.allocate_uid,
            context=fixture.handler.context,
        )
        with self.assertRaisesRegex(ValueError, "snapshot"):
            handler(
                {"effect_class": 57, "parameters": [6.0, 0.0]}, {}, fixture.invocation
            )
        self.assertEqual(fixture.packets, [])


if __name__ == "__main__":
    unittest.main()
