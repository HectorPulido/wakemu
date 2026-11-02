"""Native eXt/eXs target75 dispatcher and authentic state-owner regressions."""
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import sys, unittest, json
from unittest.mock import patch
from wakfu_server.combat_effect_dispatch import EffectDispatcher, EffectInvocation
from wakfu_server.combat_target_property_eligibility import (
    target_property_eligibility,
    special_state_container,
    _state_categories,
)
from wakfu_server.combat_native_container import state_container_scope
from test_combat_damage_handler import DamageHandlerTests
from test_combat_healing_handler import HealingHandlerTests

REVISION = "0793e23d94afe346c4ae25532417355f3dd5e290da1b0588189523b31ae5cbde"


class Target75Tests(unittest.TestCase):
    def case(self, *, heal=False, properties=(), kind=11):
        c = (HealingHandlerTests if heal else DamageHandlerTests)()
        c.setUp()
        target = c.fight.actors[-7]
        target.native_fight_property_counts = {p: 1 for p in properties}
        calls = []
        c.handler.allocate_uid = lambda: (calls.append("uid") or 99)
        c.handler.rng = lambda: (calls.append("arithmetic_rng") or 0.99)
        retention = SimpleNamespace(
            container=lambda i: (
                {"container_type": 1 if i.state_uid is not None else kind},
                0,
            )
        )
        c.handler.target_eligibility = target_property_eligibility(
            fight=c.fight, actor_authority=object(), retention=retention
        )
        effect = dict(
            c.effect,
            minimum_level=0,
            maximum_level=32767,
            parameter_count=1,
            probability_base=100,
            probability_per_level=0,
            criteria="",
            children=[],
        )

        def prepare(e, v, i):
            calls.append("prepare")
            return c.handler.prepare(e, v, i)

        d = EffectDispatcher(
            {str(c.invocation.reference): effect},
            {effect["effect_class"]: c.handler},
            resolve=lambda e, i: (i,),
            condition_context=lambda i: None,
            probability_accepts=lambda *a: (calls.append("probability_rng") or True),
            group_cells=lambda *a: (),
            actor_position=lambda identity: c.fight.actors[identity].position,
            prepare_effect=prepare,
        )
        return c, target, calls, d

    def apply_state(self, c, reference=3, uid=101):
        definition = dict(
            maximum_level=1,
            duration_base=-1,
            duration_per_level=0,
            realtime_duration_base=0,
            realtime_duration_per_level=0,
            clock_actor="target",
            tick_at_turn_end=False,
            additive=False,
            replace=False,
            refresh=False,
            protected=False,
            skip_turn_timer=False,
            effect_ids=[],
        )
        return (
            c.fight.actors[-7]
            .state_ledger.apply(
                {"states": {str(reference): definition}, "effects": {}},
                reference,
                1,
                caster_id=7,
                uid=uid,
            )
            .applied
        )

    def test_standard_damage75_skips_before_prepare_uid_rng_hp_or_packets(self):
        c, target, calls, d = self.case(properties=(75, 18))
        before = (target.hp, dict(target.effect_stats), c.fight.actors[7].ap)
        self.assertFalse(d.execute(c.invocation))
        self.assertEqual(calls, [])
        self.assertEqual(c.packets, [])
        self.assertEqual((target.hp, target.effect_stats, c.fight.actors[7].ap), before)

    def test_standard_healing75_skips_before_prepare_uid_rng(self):
        c, target, calls, d = self.case(heal=True, properties=(75,))
        before = (target.hp, dict(target.effect_stats))
        self.assertFalse(d.execute(c.invocation))
        self.assertEqual(calls, [])
        self.assertEqual((target.hp, target.effect_stats), before)
        self.assertEqual(c.packets, [])

    def test_invisibility18_alone_does_not_immunize_damage_or_healing(self):
        for heal in [False, True]:
            with self.subTest(heal=heal):
                c, target, calls, d = self.case(heal=heal, properties=(18,))
                before = target.hp
                self.assertTrue(d.execute(c.invocation))
                self.assertNotEqual(target.hp, before)
                self.assertIn("uid", calls)

    def test_authentic_active_special_state_allows_75_damage(self):
        c, target, calls, d = self.case(properties=(75,))
        state = self.apply_state(c)
        inv = replace(c.invocation, state_uid=state.uid)
        with patch("wakfu_server.native_catalog.release", return_value=REVISION):
            self.assertTrue(d.execute(inv))
        self.assertLess(target.hp, 100)
        self.assertTrue(c.packets)

    def test_removed_carrier_only_allowed_inside_its_real_retained_scope(self):
        c, target, calls, d = self.case(properties=(75,))
        state = self.apply_state(c)
        inv = replace(c.invocation, state_uid=state.uid)
        with patch("wakfu_server.native_catalog.release", return_value=REVISION):
            with state_container_scope(c.fight, {state.uid: state}):
                c.fight.actors[-7].state_ledger.remove(state.uid)
                self.assertTrue(special_state_container(c.fight, inv))
            with self.assertRaises(ValueError):
                special_state_container(c.fight, inv)

    def test_unknown_or_forged_state_uid_or_revision_remains_error(self):
        c, target, calls, d = self.case(properties=(75,))
        state = self.apply_state(c)
        with patch("wakfu_server.native_catalog.release", return_value=REVISION):
            with self.assertRaises(ValueError):
                special_state_container(c.fight, replace(c.invocation, state_uid=99999))
        with patch("wakfu_server.native_catalog.release", return_value="wrong"):
            with self.assertRaisesRegex(ValueError, "publication changed"):
                special_state_container(
                    c.fight, replace(c.invocation, state_uid=state.uid)
                )

    def test_state_container_without_authentic_uid_does_not_guess_special(self):
        c, target, calls, d = self.case(properties=(75,), kind=1)
        with self.assertRaisesRegex(ValueError, "authentic state container UID"):
            d.execute(c.invocation)
        self.assertEqual(calls, [])
        self.assertEqual(target.hp, 100)

    def test_category_file_is_complete_source_bound_and_legacy_handler_api_preserved(
        self,
    ):
        revision, ids = _state_categories()
        self.assertEqual(revision, REVISION)
        self.assertEqual(len(ids), 6129)
        c = DamageHandlerTests()
        c.setUp()
        self.assertTrue(c.handler(c.effect, {}, c.invocation))


if __name__ == "__main__":
    result = unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.loadTestsFromTestCase(Target75Tests)
    )
    sys.exit(not result.wasSuccessful())
