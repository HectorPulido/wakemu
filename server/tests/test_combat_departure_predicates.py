"""Native departure flags and actual Chafer death criterion component contract."""
import copy
import json
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from wakfu_server.combat_departure_predicates import (
    initialize_fresh_departure_flags,
    query,
    set_abandonning,
    set_fleeing,
    hydrate_fleeing_from_pW,
    restore_departure_flags,
)
from wakfu_server.combat_conditions import (
    ConditionActor,
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class DeparturePredicateTests(unittest.TestCase):
    def setUp(self):
        # No characteristic expressions occur in these predicate contracts.
        self.aliases = patch(
            "wakfu_server.combat_conditions.canonical_aliases", return_value={}
        )
        self.aliases.start()
        self.addCleanup(self.aliases.stop)

    def actor(self):
        actor = SimpleNamespace(id=-200)
        initialize_fresh_departure_flags(actor)
        return actor

    def context(self, actor):
        return ConditionContext(
            actors={
                "target": ConditionActor(
                    is_abandonning=query(actor, "abandonning"),
                    is_fleeing=query(actor, "fleeing"),
                )
            }
        )

    def test_actual_chafer_death_subscription_guard_changes_only_with_native_fields(
        self,
    ):
        actor = self.actor()
        criterion = 'not IsAbandonning("target") and not IsFleeing("target")'
        self.assertTrue(evaluate_condition(criterion, self.context(actor)))
        set_abandonning(actor, True)
        self.assertFalse(evaluate_condition(criterion, self.context(actor)))
        set_abandonning(actor, False)
        set_fleeing(actor, True)
        self.assertFalse(evaluate_condition(criterion, self.context(actor)))
        set_fleeing(actor, False)
        self.assertTrue(evaluate_condition(criterion, self.context(actor)))

    def test_unknown_actor_authority_rejected_not_false(self):
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                'IsFleeing("target")',
                ConditionContext(actors={"target": ConditionActor()}),
            )
        self.assertIsNone(query(SimpleNamespace(id=1), "fleeing"))

    def test_case_insensitive_target_missing_actor_and_default_caster(self):
        context = ConditionContext(
            actors={
                "target": ConditionActor(is_fleeing=True),
                "caster": ConditionActor(is_fleeing=False),
            }
        )
        self.assertTrue(evaluate_condition('IsFleeing("TaRgEt")', context))
        self.assertFalse(evaluate_condition("IsFleeing()", context))
        self.assertFalse(evaluate_condition('IsFleeing("other")', context))
        self.assertFalse(
            evaluate_condition('IsFleeing("target")', ConditionContext(actors={}))
        )

    def test_actual_hydration_flag_true_and_checkpoint_roundtrip(self):
        actor = self.actor()
        hydrate_fleeing_from_pW(
            actor, dict(source="native.pW.Ui", actor_id=-200, Ui=True)
        )
        from wakfu_server.fight_checkpoint_store import _plain

        snapshot = _plain(actor.native_departure_flags)
        restored = SimpleNamespace(id=-200)
        restore_departure_flags(restored, json.loads(json.dumps(snapshot)))
        self.assertTrue(query(restored, "fleeing"))
        self.assertFalse(query(restored, "abandonning"))
        set_fleeing(restored, False)
        self.assertTrue(query(actor, "fleeing"))

    def test_forged_cross_actor_and_nonboolean_hydration_fail_before_mutation(self):
        actor = self.actor()
        before = copy.deepcopy(actor.__dict__)
        for payload in [
            dict(source="native.pW.Ui", actor_id=7, Ui=True),
            dict(source="native.pW.Ui", actor_id=-200, Ui=1),
        ]:
            with self.assertRaises(ValueError):
                hydrate_fleeing_from_pW(actor, payload)
            self.assertEqual(actor.__dict__, before)
        forged = copy.deepcopy(actor.native_departure_flags)
        forged["actor_id"] = 7
        with self.assertRaises(ValueError):
            restore_departure_flags(actor, forged)
        self.assertEqual(actor.__dict__, before)

    def test_actual_snapshot_install_through_runtime_adapter_chafer_criterion(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_actor_snapshot import ActorSnapshot
        from wakfu_server.combat_runtime_adapter import (
            NativeActorAuthority,
            NativeCastAuthority,
            NativeServerRuntimeAdapter,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation

        target = Actor(-200, 1, (0, 0, 0), 176, 5, 4, 20, 20)
        hostile = Actor(-202, 0, (1, 0, 0), 176, 5, 4, 20, 20)
        fight = Fight(
            1,
            [target, hostile],
            {(0, 0, 0), (1, 0, 0)},
            {0: {(1, 0, 0)}, 1: {(0, 0, 0)}},
        )
        for actor in (target, hostile):
            stats = {1: 176, 2: 5, 3: 4, 35: 20, 92: 0, 97: 0, 100: 0}
            ActorSnapshot(
                actor.id,
                stats,
                {k: 0 for k in stats},
                dict(stats),
                frozenset(),
                0,
                "test.native.fixture",
                native_los_height=1,
                native_physical_position=actor.position,
                native_jump_height=4,
            ).install(actor)
        self.assertFalse(query(target, "abandonning"))
        empty = lambda *args: None
        cast = NativeCastAuthority(*([empty] * 10))

        def authority(preview, actor):
            return NativeActorAuthority(
                {"is_eGj": True},
                False,
                frozenset(),
                frozenset(),
                False,
                1127,
                0,
                {},
                True,
            )

        adapter = NativeServerRuntimeAdapter(actor_authority=authority, cast=cast)
        invocation = EffectInvocation(25902, 1, -200, -200, target.position)
        with patch(
            "wakfu_server.combat_characteristic_conditions.characteristic_ids",
            return_value={},
        ):
            context = adapter.condition(fight, {}, None, invocation)
            self.assertTrue(
                evaluate_condition(
                    'not IsAbandonning("target") and not IsFleeing("target")', context
                )
            )
            set_fleeing(target, True)
            context = adapter.condition(fight, {}, None, invocation)
            self.assertFalse(
                evaluate_condition(
                    'not IsAbandonning("target") and not IsFleeing("target")', context
                )
            )

    def test_boolean_float_identity_aliases_rejected(self):
        actor = SimpleNamespace(id=1)
        initialize_fresh_departure_flags(actor)
        before = copy.deepcopy(actor.__dict__)
        for identity in (True, 1.0):
            snapshot = copy.deepcopy(actor.native_departure_flags)
            snapshot["actor_id"] = identity
            with self.assertRaises(ValueError):
                restore_departure_flags(actor, snapshot)
            with self.assertRaises(ValueError):
                hydrate_fleeing_from_pW(
                    actor, dict(source="native.pW.Ui", actor_id=identity, Ui=True)
                )
            self.assertEqual(actor.__dict__, before)
            with self.assertRaises(ValueError):
                initialize_fresh_departure_flags(SimpleNamespace(id=identity))

    def test_native_signature_rejects_numeric_and_extra_arguments(self):
        for criterion in ["IsFleeing(1)", 'IsAbandonning("target",1)']:
            with self.assertRaises(UnknownCondition):
                evaluate_condition(criterion, ConditionContext(actors={}))


if __name__ == "__main__":
    unittest.main()
