"""Real existing wave-birth fixture; seeded old journal rows, not full gameplay."""
import copy
import unittest
from unittest.mock import patch

from rift_event_history_fixture import admitted_native_birth
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server import rift_dispatch_combat as baseline


class NativeEventBoundaryTests(unittest.TestCase):
    def test_native_birth_packets_and_all_serialized_state_except_exact_events_match(
        self,
    ):
        fight, runtime = admitted_native_birth(prepare_only=True)
        original = copy.deepcopy(fight.events)
        # Explicit old diagnostic journal fixture. Native actors, wave install,
        # timeline, serializers and packet production below are actual paths.
        fight.events = []
        fight.sequence = 0
        fight._event("turn_started", turn_id=fight.turn_id - 1, actor_id=1)
        for i in range(400):
            fight._event(
                "state_applied",
                actor_id=1,
                source_id=1,
                uid=10000 + i,
                state_id=1,
                level=1,
                duration=1,
                instant=True,
            )
        for event in original:
            fields = {k: v for k, v in event.items() if k not in ("sequence", "kind")}
            fight._event(event["kind"], **fields)
        baseline_fight, baseline_runtime = copy.deepcopy((fight, runtime))
        candidate_fight, candidate_runtime = copy.deepcopy((fight, runtime))
        with patch(
            "wakfu_server.combat_materialized_event_history.prune_materialized_events",
            return_value=0,
        ):
            expected = baseline.finish_accepted_action(
                baseline_fight, baseline_runtime, (), initialize_actor=lambda *a: []
            )
        actual = baseline.finish_accepted_action(
            candidate_fight, candidate_runtime, (), initialize_actor=lambda *a: []
        )
        self.assertEqual(actual.packets, expected.packets)
        before = snapshot(baseline_fight, runtime=baseline_runtime)
        after = snapshot(candidate_fight, runtime=candidate_runtime)
        original_events = before.pop("events")
        actual_events = after.pop("events")
        self.assertEqual(after, before)
        removed = {event["sequence"] for event in original_events} - {
            event["sequence"] for event in actual_events
        }
        self.assertTrue(removed)
        self.assertTrue(
            all(
                event["kind"] == "state_applied"
                for event in original_events
                if event["sequence"] in removed
            )
        )
        self.assertEqual(
            actual_events,
            [event for event in original_events if event["sequence"] not in removed],
        )
        self.assertEqual(actual_events[-256:], original_events[-256:])
        self.assertEqual(candidate_fight.sequence, baseline_fight.sequence)
        before_ack = (candidate_fight.turn_id, candidate_runtime.turn_deadline)
        self.assertEqual(
            before_ack, (baseline_fight.turn_id, baseline_runtime.turn_deadline)
        )
