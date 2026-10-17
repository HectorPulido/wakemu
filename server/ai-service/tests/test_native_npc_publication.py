"""Actual chosen NPC execution plus real server Registry publication boundaries."""
from copy import deepcopy
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

import test_native_npc_reproduction as fixtures
from wakfu_server.combat_shared import Registry, Session, Transition
from wakfu_server.combat_reproduction_state import encode_state, decode_state
from wakfu_server.combat_npc_reproduction import SCHEMA as NPC_SCHEMA, _sdk_modules
from wakfu_server.combat_npc_publication import (
    SCHEMA,
    CHOSEN,
    FALLBACK,
    UnsupportedNPCPublication,
    remember_private_commit,
    pending_private_commit,
    pending_usage,
    replay_npc_publication,
    npc_fallback_scope,
)
from wakfu_server.spells import default_deck
import wakfu_server.combat_npc_publication as publication


class PendingNativeCapsuleTests(unittest.TestCase):
    def setUp(self):
        with publication._PENDING_LOCK:
            publication._PENDING.clear()

    def test_pending_capsules_are_frozen_globally_bounded_and_weak(self):
        class Owner:
            pass

        owners = [Owner() for _ in range(3)]
        receipt = dict(schema=NPC_SCHEMA, status="accepted", private="actual-facts")
        with patch.object(publication, "MAX_PENDING_RUNTIMES", 2), patch.object(
            publication, "MAX_PENDING_BYTES", 400
        ), patch.object(publication, "MAX_CAPSULE_BYTES", 400):
            for owner in owners:
                self.assertTrue(remember_private_commit(owner, receipt))
            receipt["private"] = "mutated-after-capture"
            self.assertIsNone(pending_private_commit(owners[0]))
            self.assertEqual(
                pending_private_commit(owners[1])["private"], "actual-facts"
            )
            self.assertEqual(pending_usage()["runtimes"], 2)
            self.assertLessEqual(pending_usage()["bytes"], 400)
            owners[1] = None
            self.assertEqual(pending_usage()["runtimes"], 1)
            self.assertEqual(
                pending_private_commit(owners[2], consume=True)["status"], "accepted"
            )
            self.assertEqual(pending_usage(), dict(runtimes=0, bytes=0))

    def test_oversized_and_rejected_private_capsules_are_not_retained(self):
        class Owner:
            pass

        owner = Owner()
        with patch.object(publication, "MAX_CAPSULE_BYTES", 32):
            self.assertFalse(
                remember_private_commit(
                    owner, dict(schema=NPC_SCHEMA, status="accepted", payload="long")
                )
            )
        self.assertFalse(
            remember_private_commit(owner, dict(schema=NPC_SCHEMA, status="raised"))
        )
        self.assertIsNone(pending_private_commit(owner))

    def test_cyclic_owner_gc_under_pending_lock_cannot_deadlock(self):
        server = str(Path(__file__).resolve().parents[2])
        script = (
            "import sys; sys.path.insert(0, " + repr(server) + "); "
            "import gc; from wakfu_server.combat_npc_publication import "
            "remember_private_commit, pending_usage, _PENDING_LOCK; "
            "from wakfu_server.combat_npc_reproduction import SCHEMA; "
            "Owner = type('Owner', (), {}); owner = Owner(); owner.cycle = owner; "
            "assert remember_private_commit(owner, dict(schema=SCHEMA,status='accepted')); "
            "del owner; _PENDING_LOCK.acquire(); gc.collect(); "
            "assert pending_usage()['runtimes'] == 0; _PENDING_LOCK.release()"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c", script],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=15,
            )
        self.assertEqual(result.returncode, 0, result.stderr)


class NativeNPCPublicationTests(unittest.TestCase):
    def setUp(self):
        with publication._PENDING_LOCK:
            publication._PENDING.clear()
        self.receipts = []
        self.environment = patch.dict(
            os.environ,
            {
                "WAKFU_COMBAT_INCIDENT_DIR": "/private-test-writer-unused",
                "WAKFU_COMBAT_INCIDENT_MODE": "failures",
            },
        )
        self.writer = patch(
            "wakfu_server.combat_incident_capture._enqueue",
            side_effect=lambda root, receipt: self.receipts.append(deepcopy(receipt)),
        )
        self.environment.start()
        self.writer.start()
        self.addCleanup(self.writer.stop)
        self.addCleanup(self.environment.stop)

    def setup_shared(self, *, ready=False):
        helper = fixtures.NativeNPCReproductionTests()
        fixture, runtime, _, _, action = helper.setup_native()
        if ready:
            runtime = helper.bind_actual_ready_providers(fixture, runtime)
            action["target"] = list(fixture.pc.position)
        session = Session(
            fixture.character["account_id"],
            fixture.pc.id,
            "owned-generation",
            fixture.character["map_id"],
            0,
        )
        registry = Registry(lambda candidate: candidate == session)
        shared = registry.register(runtime.fight, session, runtime=runtime)
        shared.native_ai_turn_claim = (
            fixture.npc.id,
            runtime.fight.turn_id,
            "owned-claim",
        )
        return fixture, registry, shared, session, action

    def chosen(self, fixture, shared, action):
        native = deepcopy(shared.runtime)
        oracle_module, stats_module, _ = _sdk_modules()
        oracle = oracle_module.NativeOracle(
            native,
            characters={fixture.pc.id: fixture.character},
            monsters={fixture.npc.id: fixture.monster},
            decks={fixture.pc.id: default_deck(fixture.character)},
            excluded_decks={fixture.pc.id: frozenset()},
            viewer_id=fixture.pc.id,
            flags={},
        )
        stats = stats_module.NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=native.fight.id,
            map_id=fixture.character["map_id"],
        )
        packets = tuple(oracle.commit(action, stats_serializer=stats))
        self.assertIsNotNone(pending_private_commit(native))
        return Transition(native.fight, native, packets)

    def publish(self, registry, shared, session, transition, expected_sequence=None):
        return registry.execute_server(
            shared.fight.id,
            shared.fight.current.id,
            lambda candidate, runtime: transition,
            expected_sequence=shared.sequence
            if expected_sequence is None
            else expected_sequence,
            incident_runtime=transition.runtime,
            incident_packets=transition.packets,
            incident_session=session,
            incident_recipe=CHOSEN,
            incident_turn_id=shared.fight.turn_id,
        )

    def publication_receipt(self):
        found = [receipt for receipt in self.receipts if receipt["schema"] == SCHEMA]
        self.assertEqual(len(found), 1)
        return found[0]

    def test_default_failure_mode_retains_cast_for_stale_publication_failure(self):
        fixture, registry, shared, session, action = self.setup_shared()
        transition = self.chosen(fixture, shared, action)
        self.assertEqual(self.receipts, [])  # Accepted attack was not written.
        before = encode_state(shared.runtime)
        with self.assertRaisesRegex(ValueError, "Stale server combat sequence"):
            self.publish(registry, shared, session, transition, expected_sequence=-1)
        receipt = self.publication_receipt()
        self.assertEqual(receipt["incomplete"], [])
        self.assertIsNotNone(receipt["private_commit"])
        self.assertIsNone(receipt["transition"])
        self.assertEqual(encode_state(shared.runtime), before)
        self.assertTrue(replay_npc_publication(receipt)["matches"])
        self.assertIsNone(pending_private_commit(transition.runtime))

    def test_successful_publication_recomputes_attack_and_actual_mailboxes(self):
        fixture, registry, shared, session, action = self.setup_shared()
        hp = shared.fight.actors[fixture.pc.id].hp
        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_MODE": "all"}):
            transition = self.chosen(fixture, shared, action)
            sequence = self.publish(registry, shared, session, transition)
        self.assertEqual(sequence, 1)
        self.assertLess(shared.fight.actors[fixture.pc.id].hp, hp)
        receipt = self.publication_receipt()
        self.assertEqual(receipt["incomplete"], [])
        result = replay_npc_publication(receipt)
        self.assertTrue(result["matches"])
        self.assertFalse(result["dispatch_qualified"])
        self.assertEqual(len(shared.outboxes[session.account_id]), 1)
        self.assertEqual(
            shared.outboxes[session.account_id][0].packets, transition.packets
        )
        malformed = deepcopy(receipt)
        self.assertEqual(malformed["return_value"], 1)
        malformed["return_value"] = True
        rejected = replay_npc_publication(malformed)
        self.assertFalse(rejected["matches"])
        self.assertFalse(rejected["comparison"]["return_matches"])

    def test_pending_ack_postprocessing_rejection_replays_after_real_private_attack(
        self,
    ):
        fixture, registry, shared, session, action = self.setup_shared()
        transition = self.chosen(fixture, shared, action)
        shared.ack.arm(123, [session])
        hp = shared.fight.actors[fixture.pc.id].hp
        with self.assertRaisesRegex(ValueError, "cleared a pending shared turn ACK"):
            self.publish(registry, shared, session, transition)
        receipt = self.publication_receipt()
        self.assertIsNotNone(receipt["transition"])
        self.assertEqual(shared.fight.actors[fixture.pc.id].hp, hp)
        self.assertEqual(len(shared.outboxes[session.account_id]), 0)
        self.assertTrue(replay_npc_publication(receipt)["matches"])

    def test_registry_transition_validation_rejection_has_no_observed_transition(self):
        fixture, registry, shared, session, action = self.setup_shared()
        transition = self.chosen(fixture, shared, action)
        before = encode_state(shared.runtime)
        validate = Registry._transition.__func__
        calls = []

        def malformed_at_validation(cls, result, candidate, runtime):
            # The attack is the real selected NativeOracle commit above. Inject
            # a transport fault only at the actual Registry validation seam,
            # then invoke the production validator once in each execution.
            calls.append("validate")
            faulty = Transition(
                result.fight,
                result.runtime,
                result.packets + ((65536, b"invalid protocol opcode"),),
            )
            return validate(cls, faulty, candidate, runtime)

        with patch.object(
            Registry, "_transition", classmethod(malformed_at_validation)
        ):
            with self.assertRaises(ValueError):
                self.publish(registry, shared, session, transition)
            receipt = self.publication_receipt()
            self.assertEqual(receipt["incomplete"], [])
            self.assertIsNone(receipt["transition"])
            self.assertEqual(encode_state(shared.runtime), before)
            self.assertEqual(len(shared.outboxes[session.account_id]), 0)
            result = replay_npc_publication(receipt)
        self.assertTrue(result["matches"])
        self.assertIsNone(result["transition"])
        self.assertEqual(result["error"], receipt["error"])
        self.assertEqual(calls, ["validate", "validate"])

    def test_transition_packet_mismatch_is_explicit_unqualified_provenance(self):
        fixture, registry, shared, session, action = self.setup_shared()
        transition = self.chosen(fixture, shared, action)
        changed = Transition(
            transition.fight,
            transition.runtime,
            transition.packets + ((13420, b"different"),),
        )
        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_MODE": "all"}):
            self.publish(registry, shared, session, changed)
        receipt = self.publication_receipt()
        self.assertIn("private_commit_transition_mismatch", receipt["incomplete"])
        with self.assertRaises(UnsupportedNPCPublication):
            replay_npc_publication(receipt)

    def test_broadcast_exception_keeps_actual_after_state_and_custom_provider_is_unqualified(
        self,
    ):
        fixture, registry, shared, session, action = self.setup_shared()
        transition = self.chosen(fixture, shared, action)
        with patch.object(
            registry,
            "_broadcast",
            side_effect=RuntimeError("observed broadcast failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "observed broadcast failure"):
                self.publish(registry, shared, session, transition)
        receipt = self.publication_receipt()
        self.assertEqual(receipt["error"]["message"], "observed broadcast failure")
        self.assertIs(shared.runtime, transition.runtime)
        self.assertNotEqual(receipt["before"], receipt["after"])
        self.assertIn(
            "unqualified_registry_publication_provider", receipt["incomplete"]
        )
        with self.assertRaises(UnsupportedNPCPublication):
            replay_npc_publication(receipt)

    def test_direct_ready_fallback_uses_actual_end_server_turn_and_collective_ack(self):
        fixture, registry, shared, session, _ = self.setup_shared(ready=True)
        actor_id, turn_id = fixture.npc.id, shared.fight.turn_id

        def end_turn(candidate, runtime):
            return Transition(
                candidate, runtime, tuple(runtime.end_server_turn(actor_id, turn_id))
            )

        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_MODE": "all"}):
            registry.execute_server(
                shared.fight.id,
                actor_id,
                end_turn,
                expected_sequence=shared.sequence,
                incident_session=session,
                incident_recipe=FALLBACK,
                incident_turn_id=turn_id,
            )
        receipt = self.publication_receipt()
        self.assertEqual(receipt["incomplete"], [])
        self.assertEqual(shared.ack.turn, turn_id)
        checkpoint = decode_state(receipt["before"]["graph"])
        self.assertEqual(list(vars(checkpoint["fight"])), list(vars(fixture.fight)))
        self.assertIs(checkpoint["runtime"].fight, checkpoint["fight"])
        facts = decode_state(receipt["fallback"])
        self.assertEqual(
            facts["turn_policy"], dict(native_events=True, area_callbacks=False)
        )
        result = replay_npc_publication(receipt)
        self.assertTrue(result["matches"], result["comparison"])

    def test_private_budget_fallback_retains_diagnostic_source_and_native_oracle_providers(
        self,
    ):
        fixture, registry, shared, session, action = self.setup_shared(ready=True)
        # First publish a real chosen cast, establishing actual oracle callbacks
        # and NativeStats on the shared runtime, as the ordinary driver does.
        transition = self.chosen(fixture, shared, action)
        self.publish(registry, shared, session, transition)
        native = deepcopy(shared.runtime)
        native.native_ai_preparation_started_at = time.monotonic()
        actor_id, turn_id = native.fight.current.id, native.fight.turn_id
        with npc_fallback_scope(native, actor_id, turn_id) as capture:
            packets = tuple(native.end_server_turn(actor_id, turn_id))
            capture.packets(packets)
        self.assertIsNotNone(pending_private_commit(native))
        fresh = Transition(native.fight, native, packets)
        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_MODE": "all"}):
            registry.execute_server(
                shared.fight.id,
                actor_id,
                lambda candidate, runtime: fresh,
                expected_sequence=shared.sequence,
                incident_runtime=native,
                incident_packets=packets,
                incident_session=session,
                incident_recipe=FALLBACK,
                incident_turn_id=turn_id,
            )
        receipt = self.publication_receipt()
        self.assertEqual(receipt["incomplete"], [])
        self.assertIsNotNone(receipt["private_commit"])
        self.assertTrue(replay_npc_publication(receipt)["matches"])

    def test_evidence_writer_failure_cannot_change_real_publication(self):
        fixture, registry, shared, session, action = self.setup_shared()
        transition = self.chosen(fixture, shared, action)
        with patch.dict(os.environ, {"WAKFU_COMBAT_INCIDENT_MODE": "all"}), patch(
            "wakfu_server.combat_incident_capture._enqueue",
            side_effect=OSError("private writer unavailable"),
        ):
            self.assertEqual(self.publish(registry, shared, session, transition), 1)
        self.assertIs(shared.runtime, transition.runtime)
