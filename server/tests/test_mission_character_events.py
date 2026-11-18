"""Finite reviewed intro admission and authentic lifecycle boundaries."""

from contextlib import nullcontext
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from test_mission_toolkit_core import quest, objective, profile, state
from wakfu_server.achievements import mission_toolkit_contract as contract
from wakfu_server.achievements import mission_toolkit_planner as planner
from wakfu_server.achievements import mission_character_events as events
from wakfu_server.application import mission_character_dispatch as dispatch


def intro(identity=1, minimum=50):
    return dict(
        id=f"reviewed-intro-{identity}",
        quest_id=identity,
        event=dict(kind="character_ready", reference=0),
        minimum_level=minimum,
        admission_evidence="Reviewed positive guide level threshold; synthetic fixture.",
    )


class MissionCharacterEventTests(unittest.TestCase):
    def test_character_ready_is_opted_in_evidenced_activation_only(self):
        native = [quest(1, [objective(11)])]
        valid = profile(activations=[intro()])
        contract.validate(valid, native)
        for change in (
            {"minimum_level": None},
            {"minimum_level": True},
            {"admission_evidence": ""},
            {"event": dict(kind="character_ready")},
            {"event": dict(kind="character_ready", reference=50)},
        ):
            bad = deepcopy(valid)
            bad["activations"][0].update(change)
            with self.subTest(change=change), self.assertRaises(ValueError):
                contract.validate(bad, native)
        with self.assertRaises(ValueError):
            contract.validate_event(dict(kind="map_enter", reference=0, quantity=1))
        binding = dict(
            id="no-auto-win",
            quest_id=1,
            objective_id=11,
            event=dict(kind="character_ready", reference=0),
            count="operation",
        )
        with self.assertRaisesRegex(ValueError, "activation-only"):
            contract.validate(profile(bindings=[binding]), native)

    def test_reviewed_threshold_native_gate_scope_and_once_all_apply(self):
        native = [
            quest(1, [objective(11)], criteria="GetRealLevel() >= 50"),
            quest(2, [objective(12)]),
        ]
        declaration = profile(
            activations=[dict(intro(minimum=36), maps=[777], instances=[0])]
        )
        event = dict(kind="character_ready", reference=0, quantity=1)
        for level, map_id, expected in (
            (35, 777, []),
            (36, 777, []),
            (50, 778, []),
            (50, 777, [1]),
        ):
            after, intents, objectives, completed = planner.plan(
                state(),
                native,
                declaration,
                event,
                character=dict(id=7, level=level, map_id=map_id, instance_id=0),
                store=object(),
                now_ms=1,
            )
            self.assertEqual(after["running"], expected)
            self.assertEqual((intents, objectives, completed), ([], [], []))
            if expected:
                again = planner.plan(
                    after,
                    native,
                    declaration,
                    event,
                    character=dict(id=7, level=50, map_id=777, instance_id=0),
                    store=object(),
                    now_ms=2,
                )[0]
                self.assertEqual(again, after)
                self.assertNotIn(2, after["running"])

    def test_no_real_increase_produces_no_activation_and_reentrant_settlement_is_inert(
        self,
    ):
        current = dict(id=7, account_id=3, level=50, map_id=777, instance_id=0)
        store = SimpleNamespace(character=Mock(return_value=current))
        with patch.object(events.mission_toolkit, "settle", return_value=[]) as settle:
            self.assertEqual(events.level_changed(object(), store, current, 50), [])
            settle.assert_not_called()
        observed = []

        def nested(db, store, character, token, kind, reference):
            observed.append((kind, reference, token))
            self.assertEqual(events.level_changed(db, store, character, 49), [])
            return [(13832, b"one intro")]

        with patch.object(events.mission_toolkit, "settle", side_effect=nested):
            self.assertEqual(
                events.level_changed(object(), store, current, 49),
                [(13832, b"one intro")],
            )
        self.assertEqual(len(observed), 1)
        self.assertEqual(observed[0][:2], ("character_ready", 0))

    def test_actual_post_bootstrap_dispatcher_gates_readiness_and_keeps_optional_errors_local(
        self,
    ):
        from psycopg import Error as DatabaseError
        from psycopg_pool import PoolTimeout

        session = SimpleNamespace(
            state=SimpleNamespace(
                selected=False,
                loaded=False,
                account_id=3,
                generation="lease",
                character=dict(id=7),
                connection=object(),
                service=object(),
            ),
            runtime=SimpleNamespace(
                POSITIONS=SimpleNamespace(account_barrier=lambda _: nullcontext()),
                flush_positions=Mock(),
                STORE=object(),
                record=Mock(),
            ),
            publish_settled_quest_packets=Mock(),
        )
        with patch.object(events, "ready") as ready:
            self.assertFalse(dispatch.ready(session))
            ready.assert_not_called()
        session.state.selected = session.state.loaded = True
        for error in (
            ValueError("stale lease"),
            DatabaseError("private query"),
            PoolTimeout("private pool"),
        ):
            with self.subTest(error=type(error).__name__), patch.object(
                events, "ready", side_effect=error
            ):
                self.assertFalse(dispatch.ready(session))
                self.assertEqual(
                    session.runtime.record.call_args.kwargs["reason"],
                    type(error).__name__,
                )
        session.publish_settled_quest_packets.assert_not_called()
