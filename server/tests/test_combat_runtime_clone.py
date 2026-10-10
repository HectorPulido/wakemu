"""Transactional runtime copies keep services outside the owned state graph."""
from copy import deepcopy
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_runtime_messages import RuntimeMessages


class Service:
    def __init__(self):
        self.catalog = {"definition": [1, 2, 3]}

    def __deepcopy__(self, memo):
        raise AssertionError("External service must not enter combat clone graph")

    def invoke(self, *args, **kwargs):
        return args


class RuntimeCloneTests(unittest.TestCase):
    def test_idle_poll_before_deadline_does_not_copy_transaction_graph(self):
        from wakfu_server.combat_shared import Registry, Session, SharedFight

        actor = SimpleNamespace(controlled=True, hp=100)
        fight = SimpleNamespace(phase="active", current=actor, turn_id=1)
        runtime = RuntimeMessages(fight, clock=lambda: 29.99)
        runtime.turn_deadline, runtime.deadline_turn = 30, 1
        session = Session(1, 1, "lease", 1, 0)
        shared = SharedFight(fight, 1, 0, runtime)
        shared.participants[1] = session
        shared.connected.add(1)
        registry = Registry(lambda candidate: candidate == session)
        registry.fights[1] = shared
        with patch("wakfu_server.combat_shared.deepcopy", side_effect=AssertionError):
            self.assertEqual(
                registry.expire_current_turn(1, session, now_ms=29990),
                (False, None),
            )
        self.assertIs(shared.fight, fight)
        self.assertIs(shared.runtime, runtime)
        runtime.clock = lambda: 30
        self.assertTrue(runtime.expiration_due())
        runtime.awaiting_ack = 1
        self.assertFalse(runtime.expiration_due())

    def test_bound_services_preserve_identity_and_candidate_state_is_isolated(self):
        service = Service()
        callback = service.invoke
        fight = SimpleNamespace(actors={1: SimpleNamespace(hp=100)}, events=[])
        runtime = RuntimeMessages(
            fight,
            stats_serializer=callback,
            runtime_stats_serializer=callback,
            turn_end_provider=callback,
            turn_start_provider=callback,
            expiration_runtime_factory=callback,
            clock=callback,
        )
        runtime.pending = [(123, bytearray(b"pending"))]
        runtime.extension = {"fight": fight, "values": []}
        candidate, cloned = deepcopy((fight, runtime))
        self.assertIs(cloned.fight, candidate)
        self.assertIs(cloned.extension["fight"], candidate)
        for field in (
            "stats_serializer",
            "runtime_stats_serializer",
            "turn_end_provider",
            "turn_start_provider",
            "expiration_runtime_factory",
            "clock",
        ):
            self.assertIs(getattr(cloned, field), callback)
            self.assertIs(getattr(cloned, field).__self__.catalog, service.catalog)
        candidate.actors[1].hp = 1
        candidate.events.append("speculative")
        cloned.pending[0][1][0] = 0
        cloned.extension["values"].append("speculative")
        self.assertEqual(fight.actors[1].hp, 100)
        self.assertEqual(fight.events, [])
        self.assertEqual(runtime.pending[0][1], b"pending")
        self.assertEqual(runtime.extension["values"], [])

    def test_runtime_first_copy_preserves_cycles_and_fight_alias(self):
        fight = SimpleNamespace(events=[])
        runtime = RuntimeMessages(fight)
        runtime.extension = {"runtime": runtime, "fight": fight}
        cloned, candidate = deepcopy((runtime, fight))
        self.assertIs(cloned.fight, candidate)
        self.assertIs(cloned.extension["runtime"], cloned)
        self.assertIs(cloned.extension["fight"], candidate)
        self.assertIsNot(candidate.events, fight.events)
