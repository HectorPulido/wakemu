"""Owned turn facts never fabricate a native triggering runner."""
import unittest
from dataclasses import replace
from types import SimpleNamespace
from wakfu_server.combat_event_replay import NativeExternalEvent
from wakfu_server.combat_turn_events import (
    TURN_BOUNDARY_POLICY,
    deliver_turn_start,
    validate_turn_boundary_context,
)


class TurnBoundaryContextTests(unittest.TestCase):
    def context(self):
        return dict(
            policy=TURN_BOUNDARY_POLICY,
            actor_id=7,
            turn_id=12,
            phase="start",
            event_id=1001,
        )

    def test_owned_delivery_keeps_null_source_and_is_once_per_turn(self):
        actor = SimpleNamespace(id=7, native_turn_suppression_bits=0)
        fight = SimpleNamespace(
            current=actor,
            phase="active",
            turn_id=12,
            native_start_event_delivered=True,
            actors={7: actor, 8: SimpleNamespace(id=8)},
        )
        events = []

        def replay(event, **kwargs):
            event.validate()
            events.append(event)
            return ()

        dispatcher = SimpleNamespace(
            native_retention=SimpleNamespace(fight=fight),
            native_clone_authority=object(),
            replay_event=replay,
        )
        deliver_turn_start(dispatcher, actor_id=7)
        self.assertEqual(
            [(e.manager_actor_id, e.channel) for e in events],
            [(7, 6), (7, 60), (7, 61), (8, 61)],
        )
        for event in events:
            self.assertIsNone(event.caster_id)
            self.assertIsNone(event.target_id)
            self.assertIsNone(event.uid)
            self.assertEqual(event.turn_boundary_context, self.context())
        with self.assertRaisesRegex(ValueError, "already delivered"):
            deliver_turn_start(dispatcher, actor_id=7)

    def test_foreign_actor_stale_turn_and_wrong_phase_fail(self):
        fight = SimpleNamespace(
            current=SimpleNamespace(id=7), phase="active", turn_id=12
        )
        for change in (
            {"actor_id": 8},
            {"turn_id": 11},
            {"phase": "end"},
            {"phase": []},
            {"event_id": 1002},
            {"actor_id": True},
        ):
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_turn_boundary_context(
                    dict(self.context(), **change), fight=fight
                )

    def test_external_event_cannot_cross_bind_runner_or_event_type(self):
        event = NativeExternalEvent(
            7, (1001,), 61, turn_boundary_context=self.context()
        )
        event.validate()
        for changed in (
            replace(event, caster_id=7),
            replace(event, event_ids=(1002,)),
            replace(event, cast_boundary_context={}),
        ):
            with self.assertRaises(ValueError):
                changed.validate()
