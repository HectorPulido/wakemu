"""Publication prunes obsolete native markers without changing packet/ACK authority."""
import time
from types import SimpleNamespace
import unittest
from wakfu_server.combat_state import Fight
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_turn_receipt_history import prune_published_turn_receipts
from wakfu_server.combat_checkpoint_publication import persist_prepared


def receipt(turn, actor=7, phase="start"):
    return dict(
        turn_id=turn,
        actor_id=actor,
        phase=phase,
        event_id={"start": 1001, "end": 1002, "regeneration": 1037}[phase],
        suppressed=False,
    )


def fixture():
    fight = object.__new__(Fight)
    fight.__dict__.update(
        phase="active",
        turn_id=5,
        sequence=900,
        events=[],
        native_optional_ballot_challenge=None,
        native_encounter_terminal_cleanup_policy=None,
        native_turn_event_deliveries={
            "4:7:end": receipt(5, phase="end"),
            "5:7:start": receipt(5),
            "5:7:regeneration": receipt(5, phase="regeneration"),
        },
    )
    runtime = object.__new__(RuntimeMessages)
    runtime.__dict__.update(
        fight=fight,
        clock=time.monotonic,
        awaiting_ack=4,
        pending=[(12501, b"next-turn")],
    )
    return fight, runtime


class TurnReceiptPruningTests(unittest.TestCase):
    def test_key_turn_controls_pruning_and_unknown_future_records_survive(self):
        fight, runtime = fixture()
        del fight.native_encounter_terminal_cleanup_policy
        current = fight.native_turn_event_deliveries["5:7:start"]
        unknown = {"extension": True}
        fight.native_turn_event_deliveries.update(
            {"plugin:opaque": unknown, "3:7:end": unknown, "6:7:start": receipt(6)}
        )
        pending = runtime.pending
        packets = ((12502, b"end-turn"),)
        prune_published_turn_receipts(fight, runtime, packets)
        self.assertNotIn("4:7:end", fight.native_turn_event_deliveries)
        self.assertIs(fight.native_turn_event_deliveries["5:7:start"], current)
        self.assertIs(fight.native_turn_event_deliveries["plugin:opaque"], unknown)
        self.assertIn("3:7:end", fight.native_turn_event_deliveries)
        self.assertIn("6:7:start", fight.native_turn_event_deliveries)
        self.assertEqual(fight.sequence, 900)
        self.assertEqual(runtime.awaiting_ack, 4)
        self.assertIs(runtime.pending, pending)

    def test_historical_policy_missing_admission_and_custom_callback_keep_history(self):
        for policy in (
            "native_optional_ballot_challenge",
            "native_encounter_terminal_cleanup_policy",
        ):
            fight, runtime = fixture()
            setattr(fight, policy, {})
            original = fight.native_turn_event_deliveries
            prune_published_turn_receipts(fight, runtime, ())
            self.assertIs(fight.native_turn_event_deliveries, original)
            if policy == "native_optional_ballot_challenge":
                delattr(fight, policy)
                prune_published_turn_receipts(fight, runtime, ())
                self.assertIs(fight.native_turn_event_deliveries, original)
        fight, runtime = fixture()
        runtime.turn_end_provider = lambda: None
        prune_published_turn_receipts(fight, runtime, ())
        self.assertIn("4:7:end", fight.native_turn_event_deliveries)

    def test_final_checkpoint_writer_receives_pruned_state_and_identical_packets(self):
        fight, runtime = fixture()
        fight.rift_wave_state = {"wave": 9}
        packets = ((12502, b"end-turn"),)
        observed = []

        def writer(shared, candidate, owned_runtime, delivered):
            self.assertNotIn("4:7:end", candidate.native_turn_event_deliveries)
            self.assertIs(owned_runtime, runtime)
            self.assertIs(delivered, packets)
            observed.append(candidate)
            shared.checkpoint_revision = 1

        shared = SimpleNamespace(
            join_context={"rift_checkpoint_action": writer},
            checkpoint_revision=0,
            sequence=99,
        )
        persist_prepared(shared, fight, runtime, packets)
        self.assertEqual(observed, [fight])
        self.assertIs(shared.checkpoint_publication.fight, fight)
        self.assertEqual(shared.checkpoint_publication.sequence, 100)
