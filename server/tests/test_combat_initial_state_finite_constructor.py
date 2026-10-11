"""Direct eWu/eZk constructors preserve finite state data without a native SU."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat.combat_state import Actor, Fight
from wakfu_server.combat.combat_state_handler import NativeStateHandler
from wakfu_server.combat.combat_summon_creation import native_fresh_summon_authority
from wakfu_server.combat.combat_summon_initialization import (
    detached_summon_scope,
    install_initial_states,
)
from wakfu_server.combat.combat_summon_initial_states import initial_state_plan
from wakfu_server.combat.combat_native_timing_context import native_time_payload


class FiniteInitialConstructorTests(unittest.TestCase):
    def setUp(self):
        self.actor = Actor(-3, 1, (0, 0, 0), 100, 6, 3, 1, 1)
        pc = Actor(7, 0, (1, 0, 0), 100, 6, 3, 1, 1)
        self.fight = Fight(
            77,
            [pc, self.actor],
            {(0, 0, 0), (1, 0, 0)},
            {0: {pc.position}, 1: {self.actor.position}},
        )
        del self.fight.actors[self.actor.id]
        self.actor.team = -1
        self.authority = native_fresh_summon_authority(self.actor, 6)
        self.catalog = {
            "states": {
                "123": dict(
                    maximum_level=10,
                    duration_base=2,
                    duration_per_level=0,
                    realtime_duration_base=0,
                    realtime_duration_per_level=0,
                    clock_actor="target",
                    tick_at_turn_end=False,
                    additive=False,
                    replace=True,
                    refresh=True,
                    protected=False,
                    skip_turn_timer=False,
                    effect_ids=[],
                )
            },
            "effects": {},
        }
        self.packets, self.contexts = [], []
        self.handler = NativeStateHandler(
            self.fight,
            self.packets,
            self.catalog,
            action_id=1,
            allocate_uid=lambda: 900,
            context=lambda *a: None,
            execute_child=lambda *a: None,
        )

        def apply(handler, invocation, reference, level, **kwargs):
            self.contexts.append(kwargs["carrier_context"])
            return handler.apply_reference(
                {"effect_class": 2226}, invocation, reference, level, **kwargs
            )

        self.dispatcher = SimpleNamespace(
            native_state_handler=self.handler,
            native_retention=SimpleNamespace(apply_state_reference=apply),
        )

    def install(self, fight=None, actor=None):
        return install_initial_states(
            fight or self.fight,
            actor or self.actor,
            initial_state_plan([123, 1, 0], 1),
            runtime_factory=lambda *a: (self.dispatcher, self.packets),
        )

    def test_actual_finite_state_retains_ledger_and_wire_without_fake_turn(self):
        with detached_summon_scope(self.fight, self.actor, self.authority):
            self.install()
        (entry,) = self.actor.state_ledger.entries
        self.assertEqual(entry.duration, 2)
        self.assertTrue(entry.retained)
        self.assertIsNone(entry.timer)
        self.assertEqual(self.contexts[0].native_turn_clock, 2)
        self.assertEqual(
            self.contexts[0].timing_payload, native_time_payload(realtime_remaining=0)
        )
        self.assertIsNone(self.contexts[0].timeline)
        self.assertIn(900, self.fight.state_wire_payloads)
        self.assertEqual([p[0] for p in self.packets], [12613])
        self.assertNotIn(self.actor.id, self.fight.actors)
        self.assertEqual(self.fight.phase, "placement")
        self.assertIsNone(self.fight.current)
        self.assertEqual(
            self.actor.state_ledger.expire(
                actor_id=self.actor.id, round_number=99, phase="start"
            ),
            (),
        )

    def test_lookup_alone_cannot_attest_native_absent_su(self):
        with patch(
            "wakfu_server.combat.combat_summon_initialization.detached_actor",
            return_value=self.actor,
        ):
            with self.assertRaisesRegex(ValueError, "audited finite timeline"):
                self.install()
        self.assertEqual(self.actor.state_ledger.entries, ())

    def test_scope_for_other_fight_does_not_grant_constructor(self):
        with detached_summon_scope(self.fight, self.actor, self.authority):
            with self.assertRaisesRegex(ValueError, "actual detached summon"):
                self.install(fight=SimpleNamespace(actors={}))
        self.assertEqual(self.actor.state_ledger.entries, ())

    def test_registered_active_state_keeps_real_turn_timer(self):
        from wakfu_server.combat.combat_state_ledger import StateTimeline

        self.actor.team = 1
        self.fight.actors[self.actor.id] = self.actor
        self.fight.phase = "active"
        change = self.fight.apply_state(
            self.actor.id,
            self.actor.id,
            123,
            1,
            uid=901,
            catalog=self.catalog,
            applying_effect_has_delay=False,
            timeline=StateTimeline(1, self.actor.id, 1, 1, "active"),
        )
        self.assertIsNotNone(change.applied.timer)
        self.assertEqual(change.applied.timer.actor_id, self.actor.id)
        self.assertGreater(change.applied.timer.expiration_round, 1)

    def test_realtime_duration_remains_rejected_inside_real_scope(self):
        self.catalog["states"]["123"]["realtime_duration_base"] = 1
        with detached_summon_scope(self.fight, self.actor, self.authority):
            with self.assertRaisesRegex(ValueError, "audited finite timeline"):
                self.install()
        self.assertEqual(self.actor.state_ledger.entries, ())
        self.assertEqual(self.packets, [])


if __name__ == "__main__":
    unittest.main()
