import unittest
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_current_hp_restore import (
    restore_parameters,
    restored_percentage_amount,
    restore_additional,
)
from wakfu_server.combat_effect_removal import _identity_fields


class CurrentHPRestoreTests(unittest.TestCase):
    def restore_fixture(self, trigger):
        from wakfu_server.combat_current_hp_restore import NativeCurrentHPRestoreHandler
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_stat_handler import StatExecutionContext
        from wakfu_server.combat_restore_strategy import initialize_restore_strategy

        actor = SimpleNamespace(
            id=7,
            hp=0,
            max_hp=100,
            max_ap=6,
            max_mp=3,
            effect_stats={1: 0},
            effect_minima={1: 0},
            effect_maxima={1: 100},
            effect_frozen=frozenset(),
            native_death_status={"mwD": True},
        )
        initialize_restore_strategy(actor)
        fight = SimpleNamespace(
            id=99,
            phase="active",
            actors={7: actor},
            native_qi_slots={3: {"identity": ["actor", 7]}},
            native_global_pv_collections={"fighter_status": {"7": "OFF_PLAY"}},
        )
        packets = []
        authority = SimpleNamespace(property_counts=lambda *_: {})
        handler = NativeCurrentHPRestoreHandler(
            fight,
            packets,
            action_id=1,
            allocate_uid=lambda: 123,
            context=lambda *_: StatExecutionContext(True, True, None, False, None),
            rng=lambda: 0.5,
            authority=authority,
        )
        invocation = EffectInvocation(
            196, 1, 7, 7, (0, 0, 0), native_trigger_context=trigger
        )
        effect = dict(effect_class=196, parameters=[], parameter_count=0)
        return handler, fight, actor, packets, effect, invocation

    def test_actual_source_event1010_marks_strategy_without_reviving_population(self):
        for bits, expected in [([1010], True), ([1, 202], False)]:
            handler, fight, actor, packets, effect, invocation = self.restore_fixture(
                dict(native_events_verified=True, event_ids=bits)
            )
            before_qi = deepcopy(fight.native_qi_slots)
            before_population = deepcopy(fight.native_global_pv_collections)
            with patch(
                "wakfu_server.combat_actor_snapshot.native_actor_catalog",
                return_value={"characteristics": {"1": {"expandable": False}}},
            ):
                self.assertTrue(handler(effect, {}, invocation))
            self.assertEqual(actor.hp, 1)
            self.assertEqual(actor.native_restore_strategy["restored"], expected)
            self.assertEqual(actor.native_death_status, {"mwD": True})
            self.assertEqual(fight.native_qi_slots, before_qi)
            self.assertEqual(fight.native_global_pv_collections, before_population)
            self.assertEqual(len(packets), 1)

    def test_unknown_source_or_strategy_fails_before_resource_or_packet_mutation(self):
        for trigger, remove_strategy in [
            ({}, False),
            (dict(native_events_verified=True, event_ids=[1010]), True),
        ]:
            handler, fight, actor, packets, effect, invocation = self.restore_fixture(
                trigger
            )
            if remove_strategy:
                del actor.native_restore_strategy
            before = deepcopy(vars(actor))
            with self.assertRaisesRegex(ValueError, "source Qe.oz|strategy component"):
                handler(effect, {}, invocation)
            self.assertEqual(vars(actor), before)
            self.assertEqual(packets, [])

    def test_no_parameters_is_one_hp_and_each_optional_flag_is_exact_one(self):
        baseline = restore_parameters([], 1)
        self.assertEqual(
            (baseline["percentage_mode"], baseline["initial_amount"]), (False, 1)
        )
        for flag in (0, 1, 2, -1):
            values = restore_parameters(
                [25.0, 0.0, float(flag), 0.0, float(flag), 0.0, float(flag), 0.0], 1
            )
            self.assertEqual(values["percentage"], 25)
            self.assertEqual(
                (
                    values["require_original_controller"],
                    values["restore_virtual_hp"],
                    values["restore_ap_mp"],
                ),
                (flag == 1,) * 3,
            )

    def test_stochastic_percentage_uses_native_floor_fraction_and_minimum_one(self):
        self.assertEqual(
            restored_percentage_amount(101, 50, random_fraction=lambda: 0.1), 51
        )
        self.assertEqual(
            restored_percentage_amount(101, 50, random_fraction=lambda: 0.9), 50
        )
        self.assertEqual(restored_percentage_amount(100, -10), 1)
        with self.assertRaises(ValueError):
            restored_percentage_amount(101, 50)

    def test_additional_keeps_explicit_false_flags_and_virtual_amount(self):
        for virtual, resources in (
            (False, False),
            (True, False),
            (False, True),
            (True, True),
        ):
            self.assertEqual(
                _identity_fields(
                    restore_additional(91, virtual, resources),
                    integer_fields=(10, 17, 18),
                ),
                {10: 91, 17: int(virtual), 18: int(resources)},
            )
