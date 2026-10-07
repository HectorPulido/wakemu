"""Owner-thread native turn driver: commit barriers, budgets and fallback."""
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

_HERE = Path(__file__).resolve().parents[1]
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from wakfu_ai.native import native_turn


def runtime_fixture():
    npc = SimpleNamespace(
        id=-9, controlled=False, owner_id=None, hp=20, ap=6, mp=3, wp=2
    )
    fight = SimpleNamespace(
        phase="active", current=npc, turn_id=4, id=77, actors={-9: npc}, sequence=10
    )
    return SimpleNamespace(
        fight=fight,
        awaiting_ack=None,
        pending=[],
        action_id=50,
        tactical_encounter_id="encounter-turn-test",
    )


class FakeOracle:
    def __init__(self, runtime, *, ack_on_action=False):
        self.runtime = runtime
        self.ack_on_action = ack_on_action
        self.commits = []

    def commit(self, action, *, stats_serializer):
        self.commits.append(dict(action=action, serializer=stats_serializer))
        if action["type"] == "end_turn":
            self.runtime.fight.phase = "complete"
            self.runtime.fight.current = None
        else:
            self.runtime.fight.current.ap -= 1
            self.runtime.action_id += 1
            if self.ack_on_action:
                self.runtime.awaiting_ack = self.runtime.action_id
        return [("committed", action["type"])]


class FakeSession:
    decisions = []
    calls = 0
    catalog = "c" * 64
    catalog_references = []
    certification_modes = []

    def __init__(self, oracle, transport, exporter, **kwargs):
        type(self).calls += 1
        type(self).catalog_references.append(kwargs.get("catalog_manifest"))
        self.oracle = oracle

    def decide(self, *, certify=True):
        type(self).certification_modes.append(certify)
        value = type(self).decisions.pop(0)
        if isinstance(value, BaseException):
            raise value
        return dict(action=value, source="certified-native-test")

    def guard(self):
        return None


class NativeTurnDriverTests(unittest.TestCase):
    def setUp(self):
        FakeSession.decisions = []
        FakeSession.calls = 0
        FakeSession.catalog_references = []
        FakeSession.certification_modes = []
        self.runtime = runtime_fixture()
        self.oracle = FakeOracle(self.runtime)
        self.patchers = [
            patch.object(native_turn, "NativeOracle", return_value=self.oracle),
            patch.object(native_turn, "NativeSession", FakeSession),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()

    def run_turn(self, **overrides):
        arguments = dict(
            characters={},
            monsters={},
            decks={},
            excluded_decks={},
            viewer_id=1,
            flags={},
            transport=object(),
            exporter=object(),
            policy={},
            policy_version="policy-test",
            stats_serializer=lambda actor, fight: b"stats",
        )
        arguments.update(overrides)
        return native_turn.run_turn(self.runtime, **arguments)

    def test_real_ack_after_committed_action_stops_additional_ai_actions(self):
        self.oracle.ack_on_action = True
        FakeSession.decisions = [{"type": "cast", "spellId": 77, "level": 1}]
        generator = self.run_turn(max_actions=5)

        packets, decision = next(generator)
        self.assertEqual(packets, [("committed", "cast")])
        self.assertEqual(decision["action"]["type"], "cast")
        self.assertEqual(self.runtime.awaiting_ack, 51)
        self.assertEqual(self.runtime.fight.current.ap, 5)
        with self.assertRaises(StopIteration):
            next(generator)
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits], ["cast"]
        )
        self.assertEqual(FakeSession.calls, 1)

    def test_nonfinite_deadlines_are_rejected_before_native_queries_or_commits(self):
        for budget in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(budget=budget), self.assertRaises(ValueError):
                list(self.run_turn(budget_seconds=budget))
        self.assertEqual(FakeSession.calls, 0)
        self.assertEqual(self.oracle.commits, [])
        self.assertEqual(self.runtime.fight.current.ap, 6)

    def test_action_limit_falls_back_to_native_end_turn(self):
        FakeSession.decisions = [{"type": "move", "path": [[1, 0, 0]]}]
        generator = self.run_turn(max_actions=1)

        action_packets, decision = next(generator)
        self.assertEqual(action_packets, [("committed", "move")])
        self.assertEqual(decision["action"]["type"], "move")
        end_packets, ending = next(generator)
        self.assertEqual(end_packets, [("committed", "end_turn")])
        self.assertEqual(ending["action"], {"type": "end_turn"})
        self.assertEqual(ending["reason"], "native_action_budget_exhausted")
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits],
            ["move", "end_turn"],
        )

    def test_redecisions_reuse_complete_catalogue_and_commit_each_fresh_action(self):
        FakeSession.decisions = [
            {"type": "cast", "spellId": 77, "level": 1},
            {"type": "end_turn"},
        ]
        deliveries = list(self.run_turn())
        self.assertEqual(FakeSession.catalog_references, [None, "c" * 64])
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits],
            ["cast", "end_turn"],
        )
        self.assertEqual(len(deliveries), 2)
        self.assertEqual(FakeSession.certification_modes, [False, False])

    def test_deadline_falls_back_to_end_turn_without_query(self):
        times = iter((10.0, 12.0))
        generator = self.run_turn(
            max_actions=3, budget_seconds=1, clock=lambda: next(times)
        )

        packets, ending = next(generator)
        self.assertEqual(packets, [("committed", "end_turn")])
        self.assertEqual(ending["reason"], "native_turn_deadline_reached")
        self.assertEqual(FakeSession.calls, 0)
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits], ["end_turn"]
        )

    def test_query_failure_does_not_commit_candidate_or_spend_action_resources(self):
        FakeSession.decisions = [ValueError("native query rejected")]
        generator = self.run_turn(max_actions=3)

        packets, failure = next(generator)
        self.assertEqual(packets, [])
        self.assertEqual(failure["reason"], "native_ai_query_or_commit_rejected")
        self.assertEqual(failure["detail"], "native query rejected")
        self.assertEqual(failure["stage"], "decision_search")
        self.assertEqual(failure["turnBudgetMs"], 10000)
        self.assertGreaterEqual(failure["elapsedMs"], 0)
        self.assertEqual(self.runtime.fight.current.ap, 6)
        self.assertEqual(self.runtime.action_id, 50)
        end_packets, ending = next(generator)
        self.assertEqual(end_packets, [("committed", "end_turn")])
        self.assertEqual(ending["action"], {"type": "end_turn"})
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits], ["end_turn"]
        )

    def test_immediate_handoff_still_requires_authoritative_commit_acceptance(self):
        FakeSession.decisions = [{"type": "cast", "spellId": 77, "level": 1}]
        commit = self.oracle.commit

        def reject_cast(action, *, stats_serializer):
            if action["type"] == "cast":
                raise ValueError("native live cast is illegal")
            return commit(action, stats_serializer=stats_serializer)

        with patch.object(self.oracle, "commit", reject_cast):
            deliveries = list(self.run_turn())
        self.assertEqual(FakeSession.certification_modes, [False])
        self.assertEqual(deliveries[0][0], [])
        self.assertEqual(deliveries[0][1]["detail"], "native live cast is illegal")
        self.assertEqual(self.runtime.fight.actors[-9].ap, 6)
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits], ["end_turn"]
        )

    def test_changed_source_after_decision_cannot_reach_commit(self):
        FakeSession.decisions = [{"type": "cast", "spellId": 77, "level": 1}]
        with patch.object(
            FakeSession, "guard", side_effect=ValueError("source changed before commit")
        ):
            deliveries = list(self.run_turn())
        self.assertEqual(deliveries[0][1]["detail"], "source changed before commit")
        self.assertEqual(self.runtime.fight.actors[-9].ap, 6)
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits], ["end_turn"]
        )

    def test_decision_returning_after_deadline_never_commits_its_action(self):
        now = [10.0]

        def late_decision(session, *, certify=True):
            now[0] = 14.0
            return dict(action={"type": "cast", "spellId": 77, "level": 1})

        cancelled = []
        with patch.object(FakeSession, "decide", late_decision), patch.object(
            FakeSession,
            "cancel",
            lambda session: cancelled.append(session),
            create=True,
        ):
            deliveries = list(self.run_turn(budget_seconds=3, clock=lambda: now[0]))
        self.assertEqual(
            [entry["action"]["type"] for entry in self.oracle.commits], ["end_turn"]
        )
        self.assertEqual(self.runtime.fight.actors[-9].ap, 6)
        self.assertEqual(deliveries[0][1]["error"], "TimeoutError")
        self.assertEqual(len(cancelled), 1)


if __name__ == "__main__":
    unittest.main()
