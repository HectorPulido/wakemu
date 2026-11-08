"""Orphaned terminal presentation retirement, never a synthetic client ACK."""
from copy import deepcopy
import unittest
from unittest.mock import patch
from wakfu_server.combat_shared import Session, PendingWorldRecovery
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_terminal_retry import pending_terminal_settlement
import test_combat_shared as shared_fixtures


class TerminalFreshWorldRetirementTests(unittest.TestCase):
    def setUp(self):
        self.case = shared_fixtures.SharedCombatTests()
        self.case.setUp()
        self.case.join()
        self.shared = self.case.shared
        self.registry = self.case.registry
        self.shared.fight.phase, self.shared.fight.winner = "finished", 1
        self.shared.runtime = RuntimeMessages(self.shared.fight)
        self.shared.runtime.awaiting_ack = 42
        self.shared.runtime.pending = [(13827, b"committed-start-reaction")]
        self.shared.ack.arm(42, (self.case.one, self.case.two))
        self.shared.reconnect_turn_end_packets = ((12502, b"original-presentation"),)
        self.replacement = Session(1, 10, "terminal-world-new", 1134, 0)

    def depart(self, *, all_owners=True):
        self.registry.disconnect(self.case.one)
        self.case.live.discard(self.case.one)
        if all_owners:
            self.registry.disconnect(self.case.two)
            self.case.live.discard(self.case.two)
        self.case.live.add(self.replacement)

    def takeover(self, persist=lambda previous: None):
        return self.registry.takeover(
            99,
            self.replacement,
            lambda *args: (),
            persist_takeover=persist,
            recover_disconnected=True,
            fresh_world=True,
        )

    def test_orphan_retirement_preserves_outcome_and_enables_normal_settlement(self):
        self.depart()
        old_fight, old_runtime, old_ack = (
            self.shared.fight,
            self.shared.runtime,
            self.shared.ack,
        )

        def facts(fight):
            return (
                fight.phase,
                fight.winner,
                fight.turn_id,
                fight.sequence,
                deepcopy(fight.events),
                [
                    (
                        actor.id,
                        actor.hp,
                        actor.position,
                        tuple(actor.state_ledger.entries),
                    )
                    for actor in fight.actors.values()
                ],
            )

        before = facts(old_fight)

        def persist(previous):
            self.assertEqual(previous, self.case.one)
            self.assertIs(self.shared.fight, old_fight)
            self.assertIs(self.shared.runtime, old_runtime)
            self.assertEqual(old_runtime.awaiting_ack, 42)
            self.assertEqual(old_ack.turn, 42)

        with patch.object(
            RuntimeMessages,
            "acknowledge_turn",
            side_effect=AssertionError("No invented ACK"),
        ):
            self.takeover(persist)
        self.assertEqual(facts(self.shared.fight), before)
        self.assertIsNot(self.shared.runtime, old_runtime)
        self.assertIsNone(self.shared.runtime.awaiting_ack)
        self.assertEqual(self.shared.runtime.pending, [])
        self.assertIsNone(self.shared.ack.turn)
        self.assertEqual(self.shared.ack.received, set())
        self.assertIsNone(self.shared.reconnect_turn_end_packets)
        self.assertEqual(old_runtime.awaiting_ack, 42)
        self.assertTrue(pending_terminal_settlement(self.shared))
        self.assertIsInstance(
            self.shared.pending_world_recoveries[1], PendingWorldRecovery
        )
        self.assertEqual(self.registry.drain(99, self.replacement), [])

    def test_old_connected_recipient_retains_its_real_ack(self):
        self.depart(all_owners=False)
        runtime, barrier = self.shared.runtime, self.shared.ack
        self.takeover()
        self.assertIs(self.shared.runtime, runtime)
        self.assertIs(self.shared.ack, barrier)
        self.assertEqual(runtime.awaiting_ack, 42)
        self.assertEqual(barrier.expected, {2: self.case.two.generation})
        self.assertFalse(pending_terminal_settlement(self.shared))

    def test_persistence_failure_does_not_adopt_private_retirement(self):
        self.depart()
        fight, runtime, ack = self.shared.fight, self.shared.runtime, self.shared.ack

        def fail(previous):
            raise ValueError("durable takeover failed")

        with self.assertRaisesRegex(ValueError, "durable takeover failed"):
            self.takeover(fail)
        self.assertIs(self.shared.fight, fight)
        self.assertIs(self.shared.runtime, runtime)
        self.assertIs(self.shared.ack, ack)
        self.assertEqual(runtime.awaiting_ack, 42)
        self.assertNotIn(1, self.shared.pending_world_recoveries)
        self.assertEqual(self.shared.participants[1], self.case.one)

    def test_stale_generation_and_counter_mismatch_fail_before_persistence(self):
        for mutation in ("generation", "counter"):
            with self.subTest(mutation=mutation):
                self.setUp()
                self.depart()
                if mutation == "generation":
                    self.shared.ack.expected[2] = "foreign-generation"
                else:
                    self.shared.ack.turn = 43
                with self.assertRaises(ValueError):
                    self.takeover(lambda _: self.fail("Invalid evidence persisted"))
                self.assertEqual(self.shared.runtime.awaiting_ack, 42)

    def test_active_fight_never_uses_terminal_retirement(self):
        self.depart()
        self.shared.fight.phase, self.shared.fight.winner = "active", None
        with self.assertRaisesRegex(ValueError, "unsettled terminal PvE"):
            self.takeover(lambda _: self.fail("Active retirement persisted"))
        self.assertEqual(self.shared.runtime.awaiting_ack, 42)

    def test_orphan_retirement_requires_durable_takeover(self):
        self.depart()
        with self.assertRaisesRegex(ValueError, "durable takeover"):
            self.registry.takeover(
                99, self.replacement, lambda *args: (), fresh_world=True
            )
        self.assertEqual(self.shared.runtime.awaiting_ack, 42)

    def test_last_scene_departure_retires_both_reconnect_interleavings(self):
        for disconnect_first in (True, False):
            with self.subTest(disconnect_first=disconnect_first):
                self.setUp()
                if disconnect_first:
                    self.registry.disconnect(self.case.one)
                self.case.live.discard(self.case.one)
                self.case.live.add(self.replacement)
                self.takeover()
                self.assertFalse(pending_terminal_settlement(self.shared))
                self.assertEqual(
                    self.shared.ack.expected,
                    {2: self.case.two.generation}
                    if disconnect_first
                    else {1: self.replacement.generation, 2: self.case.two.generation},
                )
                with patch.object(
                    RuntimeMessages,
                    "acknowledge_turn",
                    side_effect=AssertionError("No invented ACK"),
                ):
                    self.registry.disconnect(self.case.two)
                self.assertTrue(pending_terminal_settlement(self.shared))
                self.assertIsNone(self.shared.ack.turn)
                self.assertEqual(self.shared.connected, {1})
                self.assertEqual(self.shared.fight.winner, 1)

    def test_departure_persistence_failure_keeps_terminal_presentation_pending(self):
        self.depart(all_owners=False)
        self.takeover()
        fight, runtime, barrier = (
            self.shared.fight,
            self.shared.runtime,
            self.shared.ack,
        )
        with patch(
            "wakfu_server.combat_checkpoint_publication.persist_prepared",
            side_effect=ValueError("checkpoint write failed"),
        ):
            with self.assertRaisesRegex(ValueError, "checkpoint write failed"):
                self.registry.disconnect(self.case.two)
        self.assertIs(self.shared.fight, fight)
        self.assertIs(self.shared.runtime, runtime)
        self.assertIs(self.shared.ack, barrier)
        self.assertEqual(runtime.awaiting_ack, 42)
        self.assertEqual(self.shared.connected, {1})

    def test_stale_world_token_cannot_remove_current_presentation_obligation(self):
        for disconnect_first in (True, False):
            with self.subTest(disconnect_first=disconnect_first):
                self.setUp()
                if disconnect_first:
                    self.registry.disconnect(self.case.one)
                self.case.live.discard(self.case.one)
                self.case.live.add(self.replacement)
                self.takeover()
                self.shared.pending_world_recoveries[1] = PendingWorldRecovery(
                    self.case.one, 99
                )
                with patch.object(
                    RuntimeMessages,
                    "acknowledge_turn",
                    side_effect=AssertionError("No invented ACK"),
                ):
                    if disconnect_first:
                        with self.assertRaisesRegex(
                            ValueError, "world-return ownership"
                        ):
                            self.registry.disconnect(self.case.two)
                        self.assertEqual(
                            self.shared.ack.expected, {2: self.case.two.generation}
                        )
                    else:
                        self.registry.disconnect(self.case.two)
                        self.assertEqual(
                            self.shared.ack.expected, {1: self.replacement.generation}
                        )
                self.assertEqual(self.shared.runtime.awaiting_ack, 42)
                self.assertFalse(pending_terminal_settlement(self.shared))
