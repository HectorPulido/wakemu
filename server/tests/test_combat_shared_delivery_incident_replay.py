"""Real native snapshot/action bytes connect replayed Registry to delivery proof.

The existing-participant recovery producer supplies the preceding native
snapshot. Original Registry delivery callbacks run against an in-memory send
sink; no sockets are opened and client reconstruction is never certified.
"""
import ast
import copy
import os
import struct
import unittest
from unittest.mock import patch

from wakfu_server.combat_cast import decode_cast
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_death import death_messages
from wakfu_server.combat_reproduction import controlled_environment
from wakfu_server.combat_reproduction_state import decode_state, encode_state
from wakfu_server.combat_incident_replay import LIVE_RECIPE, replay_shared_incident
from wakfu_server.combat_delivery_reproduction import verify_delivery_evidence
import wakfu_server.combat_delivery_observation as delivery
import test_combat_shared_action_incident_replay as action_fixture
import test_combat_incident_dispatch_integration as dispatch_fixture


class SharedDeliveryIncidentReplayTests(unittest.TestCase):
    def capture_and_replay(self):
        sent, receipts = [], []
        history = delivery.DeliveryHistory()
        with controlled_environment(action_fixture.CLOCKS, action_fixture.POLICIES):
            (
                adapter,
                shared,
                session,
                namespace,
            ) = action_fixture.SharedActionIncidentReplayTests().fixture("spell")
            with patch.dict(
                os.environ,
                {
                    "WAKFU_COMBAT_INCIDENT_DIR": "/private/native-delivery-fixture",
                    "WAKFU_COMBAT_INCIDENT_MODE": "all",
                    "WAKFU_COMBAT_START_EVENTS": "1",
                },
            ), patch.object(delivery, "_HISTORY", history), patch(
                "wakfu_server.combat_incident_capture._enqueue",
                side_effect=lambda root, receipt: receipts.append(receipt),
            ):
                # A real server recovery is valid for this already registered
                # owner. It changes native action/deadline counters normally;
                # the action below captures that resulting authoritative state.
                snapshot = tuple(
                    shared.runtime.recover(
                        session.account_id,
                        struct.pack(">i", shared.fight.id),
                        now_ms=action_fixture.CLOCKS["wall_time_ns"] // 1_000_000,
                    )
                )
                self.assertTrue(snapshot)
                recovery = next(
                    payload for opcode, payload in snapshot if opcode == 12053
                )
                self.assertEqual(struct.unpack_from(">i", recovery)[0], shared.fight.id)
                self.assertGreater(struct.unpack_from(">h", recovery, 4)[0], 0)
                self.assertIn(12873, [opcode for opcode, payload in snapshot])
                delivery.record_bootstrap(
                    shared.fight.id,
                    session,
                    snapshot,
                    producer="RuntimeMessages.recover-existing-participant-native-snapshot",
                )

                def send(actual_session, batches):
                    sent.append(
                        (
                            actual_session,
                            tuple((batch.sequence, batch.packets) for batch in batches),
                        )
                    )

                snapshot_sequence = adapter.registry.publish(
                    shared.fight.id, session, snapshot
                )
                adapter.registry.dispatch_connected(shared.fight.id, send)
                self.assertEqual(sent[0], (session, ((snapshot_sequence, snapshot),)))
                self.assertFalse(shared.outboxes[session.account_id])

                target = shared.fight.actors[-7].position
                body = struct.pack(">qqiih", 7, (7 << 32) | 6266, *target)
                namespace.update(
                    body=body,
                    cast_request=decode_cast(body),
                    prepare_server_spell=prepare_server_spell,
                    commit_spell_transaction=commit_spell_transaction,
                    authoritative_visible=authoritative_visible,
                    death_messages=death_messages,
                )
                tree = ast.Module(
                    body=[
                        copy.deepcopy(
                            dispatch_fixture.dispatcher_function("shared_cast")
                        )
                    ],
                    type_ignores=[],
                )
                exec(
                    compile(
                        ast.fix_missing_locations(tree),
                        str(dispatch_fixture.SOURCE),
                        "exec",
                    ),
                    namespace,
                )
                action_sequence = adapter.registry.execute(
                    shared.fight.id,
                    session,
                    7,
                    namespace["shared_cast"],
                    incident_request=dict(opcode=13260, body=body),
                )
                adapter.registry.dispatch_connected(shared.fight.id, send)
                self.assertEqual(len(sent), 2)
                self.assertEqual(sent[1][0], session)
                self.assertEqual(sent[1][1][0][0], action_sequence)
                self.assertFalse(shared.outboxes[session.account_id])

                shared_receipts = [
                    row
                    for row in receipts
                    if row["schema"] == "wakemu-shared-combat-incident-v1"
                ]
                sidecars = [
                    row for row in receipts if row["schema"] == delivery.SIDECAR_SCHEMA
                ]
                self.assertEqual(len(shared_receipts), 1)
                self.assertEqual(len(sidecars), 2)  # Prior snapshot, then action.
                receipt, sidecar = shared_receipts[0], sidecars[1]
                receipt[
                    "origin"
                ] = "actual-native-existing-participant-snapshot-and-dispatcher-fixture"
                preceding = decode_state(receipt["preceding_delivery_history"])
                stream = preceding["streams"][0]
                self.assertEqual(stream["bootstrap"]["packets"], snapshot)
                self.assertEqual(
                    stream["bootstrap"]["producer"],
                    "RuntimeMessages.recover-existing-participant-native-snapshot",
                )
                self.assertEqual(
                    [row["kind"] for row in stream["events"]],
                    ["bootstrap", "enqueue", "drain", "dispatch_attempt"],
                )
                self.assertTrue(receipt["bootstrap_available"])
                self.assertTrue(receipt["delivery_history_continuous"])
                before = decode_state(receipt["before"]["graph"])
                after = decode_state(receipt["after"]["graph"])
                self.assertLess(
                    after["fight"].actors[-7].hp, before["fight"].actors[-7].hp
                )
                self.assertLess(
                    after["fight"].actors[7].ap, before["fight"].actors[7].ap
                )
                self.assertEqual(
                    after["outboxes"][session.account_id][0].packets, sent[1][1][0][1]
                )

                recomputed = []
                summary = replay_shared_incident(
                    receipt,
                    provider_recipe=LIVE_RECIPE,
                    evidence_sink=recomputed.append,
                )
                self.assertTrue(summary["operation_matches"], summary["differences"])
                self.assertTrue(summary["mailbox_matches"])
                self.assertEqual(len(recomputed), 1)
                # Offline replay inherited enabled capture, but must neither
                # call the send sink nor emit a diagnostic receipt recursively.
                self.assertEqual(len(sent), 2)
                self.assertEqual(len(receipts), 3)
                return receipt, sidecar, recomputed[0], summary

    def test_native_snapshot_action_dispatch_and_recomputed_mailboxes_qualify(self):
        receipt, sidecar, after, summary = self.capture_and_replay()
        original = copy.deepcopy((receipt, sidecar, after))
        result = verify_delivery_evidence(
            receipt, [sidecar], expected_after=after, replay_outcome=summary
        )
        self.assertTrue(result["shared_delivery_qualified"], result["findings"])
        self.assertTrue(result["bootstrap_qualified"])
        self.assertTrue(result["dispatch_order_qualified"])
        self.assertTrue(result["replay_mailboxes_compared"])
        self.assertFalse(result["client_receipt_confirmed"])
        self.assertFalse(result["client_reconstruction_verified"])
        self.assertEqual((receipt, sidecar, after), original)

    def test_real_delivery_tampering_missing_snapshot_and_missing_ordinal_stay_unqualified(
        self,
    ):
        receipt, sidecar, after, summary = self.capture_and_replay()
        for mode in ("tampered-bytes", "missing-bootstrap", "missing-ordinal"):
            with self.subTest(mode=mode):
                changed_receipt, changed_sidecar = copy.deepcopy(
                    receipt
                ), copy.deepcopy(sidecar)
                if mode == "missing-bootstrap":
                    history = decode_state(
                        changed_receipt["preceding_delivery_history"]
                    )
                    history["streams"][0].update(
                        bootstrap=None, bootstrap_missing=True, history_gap=True
                    )
                    changed_receipt["preceding_delivery_history"] = encode_state(
                        history
                    )
                else:
                    attempts = decode_state(changed_sidecar["attempts"])
                    if mode == "missing-ordinal":
                        attempts[0].pop("observation_id")
                    else:
                        batch = attempts[0]["batches"][0]
                        opcode, payload = batch["packets"][0]
                        batch["packets"] = (
                            (opcode, payload + b"tampered"),
                            *batch["packets"][1:],
                        )
                    changed_sidecar["attempts"] = encode_state(attempts)
                result = verify_delivery_evidence(
                    changed_receipt,
                    [changed_sidecar],
                    expected_after=after,
                    replay_outcome=summary,
                )
                self.assertFalse(result["shared_delivery_qualified"])
                self.assertFalse(result["client_reconstruction_verified"])
                self.assertTrue(result["findings"])
