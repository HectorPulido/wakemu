"""Actual fresh player snapshots, native dsA writes and loaded status custody."""

from copy import deepcopy
from dataclasses import replace
import json
import os
from types import SimpleNamespace
import unittest


@unittest.skipUnless(
    os.environ.get("WAKFU_RIFT_CARRIER_DATASET"),
    "Explicit bounded native projection required",
)
class NativePlayerDeathConstructorComponentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_rift_native_carrier_component import NativeRiftCarrierComponentTests

        NativeRiftCarrierComponentTests.setUpClass()
        cls.carrier = NativeRiftCarrierComponentTests()

    def test_fresh_player_native_death_kill_tamper_and_loaded_state(self):
        from wakfu_server.combat_native_death_status import (
            fresh_player_death_constructor,
            initialize_fresh_player_death_status,
            initialize_fresh_bje_death_status,
            native_is_dead,
        )
        from wakfu_server.combat_actor_snapshot import build_player_snapshot
        from wakfu_server.combat_state import Actor
        from wakfu_server.equipment_stats import combat_resources
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_conditions import evaluate_condition
        from wakfu_server.combat_runtime_messages import RuntimeMessages
        from wakfu_server.combat_death import death_messages
        from wakfu_server.combat_controller_registry import current_native_team
        from wakfu_server.fight_checkpoint_store import snapshot

        component = self.carrier.fixture(1, controller_registration=True)
        fight = component.fight
        actor = fight.actors[7]
        self.assertEqual(
            (current_native_team(fight, 7), current_native_team(fight, -200)), (1, 0)
        )
        self.assertEqual(actor.native_death_status["source"], "fresh.bjo.constructor")
        self.assertEqual(actor.native_death_status["actor_kind"], "bjo")
        self.assertIsNone(actor.native_death_status["dtM_status"])
        self.assertFalse(native_is_dead(actor))
        original_hp = actor.hp
        actor.hp = 0
        self.assertFalse(native_is_dead(actor))  # HP never supplies the result.
        actor.hp = original_hp
        dispatcher, _ = component.factory(fight)
        context = dispatcher.condition_context(
            EffectInvocation(315255, 1, 7, 7, actor.position)
        )
        self.assertTrue(evaluate_condition('not IsDead("target")', context))
        self.assertFalse(
            any(
                getattr(npc, "native_death_status", {}).get("source")
                == "fresh.bjo.constructor"
                for npc in (fight.actors[-200], fight.actors[-201])
            )
        )
        before = snapshot(fight)
        with self.assertRaises(ValueError):
            initialize_fresh_player_death_status(
                actor, constructor=fresh_player_death_constructor(actor.id)
            )
        self.assertEqual(snapshot(fight), before)

        character = component.characters[7]
        resources = combat_resources(character)

        def new_snapshot():
            fresh = Actor(
                7,
                1,
                (0, 0, 0),
                character["hp"],
                resources["ap"],
                resources["mp"],
                resources["initiative"],
                100,
                owner_id=3,
                controlled=True,
                max_hp=character["max_hp"],
            )
            native = build_player_snapshot(
                character,
                fresh,
                wp_current=resources["wp"],
                wp_maximum=resources["wp"],
                running_effects=(),
            )
            return fresh, native

        for changes in ({"actor_id": 999}, {"world_properties": (19,)}):
            fresh, native = new_snapshot()
            invalid = replace(
                native,
                native_player_death_constructor=replace(
                    native.native_player_death_constructor, **changes
                ),
            )
            with self.subTest(tamper=changes), self.assertRaises(ValueError):
                invalid.install(fresh)
            self.assertIsNone(fresh.effect_stats)
            self.assertFalse(hasattr(fresh, "native_death_status"))
        fresh, native = new_snapshot()
        fresh.controlled = False
        with self.assertRaises(ValueError):
            native.install(fresh)
        self.assertIsNone(fresh.effect_stats)
        npc = SimpleNamespace(hp=0, native_world_properties=frozenset())
        initialize_fresh_bje_death_status(npc)
        self.assertFalse(native_is_dead(npc))
        npc.native_death_status["actor_kind"] = "bjo"
        with self.assertRaises(ValueError):
            native_is_dead(npc)

        for status, world, expected in (
            (
                dict(
                    source="fresh.bjo.constructor",
                    actor_kind="bjo",
                    mwD=False,
                    dtM_status=4,
                    last_writer="owned.story.setter",
                ),
                frozenset(),
                True,
            ),
            (
                dict(
                    source="fresh.bjo.constructor",
                    actor_kind="bjo",
                    mwD=True,
                    dtM_status=None,
                    last_writer="owned.aTS.F.type2",
                ),
                frozenset(),
                True,
            ),
            (
                dict(
                    source="fresh.bjo.constructor",
                    actor_kind="bjo",
                    mwD=False,
                    dtM_status=2,
                    last_writer="owned.story.setter",
                ),
                frozenset({19}),
                True,
            ),
            (None, frozenset(), None),
        ):
            fresh, native = new_snapshot()
            fresh.native_death_status = deepcopy(status)
            fresh.native_world_properties = world
            fresh.native_world_property_counts = {identity: 1 for identity in world}
            saved = deepcopy(fresh.native_death_status)
            native.install(fresh)
            self.assertEqual(fresh.native_death_status, saved)
            self.assertEqual(fresh.native_world_properties, world)
            self.assertEqual(native_is_dead(fresh), expected)
        tampered = deepcopy(actor)
        tampered.native_death_status["actor_kind"] = "bje"
        with self.assertRaises(ValueError):
            native_is_dead(tampered)

        # Actual trusted FSM damage retires the player. Native state2, rather
        # than HP0 or KO alone, finalizes dsA through the ordinary wire producer.
        fight.apply_effect_damage(-200, 7, actor.hp)
        runtime = RuntimeMessages(fight)
        packets = death_messages(runtime, 7, fighter_state=2)
        self.assertIn(12727, [opcode for opcode, _ in packets])
        self.assertTrue(native_is_dead(actor))
        self.assertEqual(actor.native_death_status["last_writer"], "owned.aTS.F.type2")
        saved = json.loads(json.dumps(snapshot(fight)))
        self.assertEqual(
            saved["actors"]["7"]["native_death_status"], actor.native_death_status
        )
        restored = deepcopy(fight)
        self.assertTrue(native_is_dead(restored.actors[7]))
        self.assertEqual(
            restored.actors[7].native_death_status, actor.native_death_status
        )
