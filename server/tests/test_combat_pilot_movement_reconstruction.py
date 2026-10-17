"""Exact stream proof binding negatives and optional actual native pilot cases."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_pilot_movement_reconstruction import (
    verify_native_movement_delivery,
)
from wakfu_server.combat_protocol_reconstruction import Recipient


def initial(actor, cell):
    admission = (
        struct.pack(">ibqqq", 99, 2, 0, 0, 0)
        + struct.pack(">ihqqBb", 0, 0, actor, 0, 1, 1)
        + struct.pack(">qbbb", actor, 0, 0, 0)
        + b"\x00\x00\x00"
        + struct.pack(">i", 0)
    )
    positions = struct.pack(">ihqiihB", 99, 1, actor, *cell, 1)
    return ((12847, admission), (13652, positions))


class MovementProofBindingTests(unittest.TestCase):
    """Synthetic receipts test validation only, never establish native trust."""

    def setUp(self):
        self.payload = struct.pack(">iiiqbb", 99, 7, -1, 22, 1, 0) + struct.pack(
            ">iihiih", 2, -3, 4, 4, -3, 4
        )
        self.updates = ((13624, self.payload), (13420, struct.pack(">i", 99)))
        self.proof = dict(
            schema="wakemu-pilot-movement-native-proof-v1",
            complete=True,
            source_stable=True,
            instrumentation="none",
            compile_returncode=0,
            classpath={"client/lib/wakfu-client.jar": "a" * 64},
            source={"sniffer/java/VerifyPilotMovementQueue.java": "b" * 64},
            cases=[
                dict(
                    id="synthetic-binding-only",
                    opcode=13624,
                    payload_sha256=hashlib.sha256(self.payload).hexdigest(),
                    initial_position=[2, -3, 4],
                    complete=True,
                    returncode=0,
                    native=dict(
                        completed_normally=True,
                        queue_drained=True,
                        action_id=7,
                        actor_id=22,
                        native_completed_action_ids=[7],
                        native_path=[[2, -3, 4], [4, -3, 4]],
                        executed_position=[4, -3, 4],
                    ),
                )
            ],
        )

    def verify(self, proof=None, updates=None, trusted=True):
        raw = json.dumps(self.proof if proof is None else proof).encode()
        return verify_native_movement_delivery(
            bootstrap=initial(22, (2, -3, 4)),
            packets=self.updates if updates is None else updates,
            recipient=Recipient("participant", "binding-only"),
            projection={"positions": {22: dict(cell=(4, -3, 4), direction=1)}},
            proof_bytes=raw,
            trusted_proof_sha256=hashlib.sha256(raw).hexdigest() if trusted else None,
        )

    def test_bound_synthetic_structure_exercises_model_without_native_trust_claim(self):
        result = self.verify()
        self.assertTrue(result["qualified"], result)
        self.assertFalse(result["rendering_qualified"])

    def test_unpinned_receipt_cannot_self_qualify(self):
        self.assertFalse(self.verify(trusted=False)["qualified"])

    def test_native_position_identity_path_and_callback_mismatches_reject(self):
        for field, value in (
            ("actor_id", 999),
            ("action_id", 8),
            ("native_completed_action_ids", []),
            ("queue_drained", False),
            ("executed_position", [3, -3, 4]),
            ("native_path", []),
        ):
            with self.subTest(field=field):
                changed = copy.deepcopy(self.proof)
                changed["cases"][0]["native"][field] = value
                self.assertFalse(self.verify(changed)["qualified"])

    def test_initial_actor_position_must_match_exact_native_case(self):
        changed = copy.deepcopy(self.proof)
        changed["cases"][0]["initial_position"] = [99, 99, 0]
        self.assertFalse(self.verify(changed)["qualified"])

    def test_missing_fence_stays_pending_despite_actual_action_callback(self):
        result = self.verify(updates=self.updates[:1])
        self.assertFalse(result["qualified"])
        self.assertTrue(result["pending"])

    def test_boolean_returncode_cannot_replace_native_zero(self):
        changed = copy.deepcopy(self.proof)
        changed["cases"][0]["returncode"] = False
        self.assertFalse(self.verify(changed)["qualified"])


class ActualNativeMovementProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_PILOT_MOVEMENT_NATIVE_PROOF")
        if not configured:
            raise unittest.SkipTest("Exact native movement pilot proof not configured")
        cls.root = Path(configured)
        cls.raw = (cls.root / "proof.json").read_bytes()
        cls.proof = json.loads(cls.raw)

    def test_actual_old_new_server_movement_cases_converge_independently(self):
        self.assertTrue(self.proof["complete"])
        for index, case in enumerate(self.proof["cases"]):
            with self.subTest(case=case["id"]):
                native = case["native"]
                payload = (self.root / f"movement-{index}.bin").read_bytes()
                actor = native["actor_id"]
                opcode_fight = struct.unpack_from(">i", payload)[0]
                # The original compact bootstrap is fixture input; its fight
                # identity is adapted explicitly to the actual action header.
                bootstrap = tuple(
                    (op, struct.pack(">i", opcode_fight) + body[4:])
                    for op, body in initial(actor, case["initial_position"])
                )
                result = verify_native_movement_delivery(
                    bootstrap=bootstrap,
                    packets=(
                        (13624, payload),
                        (13420, struct.pack(">i", opcode_fight)),
                    ),
                    recipient=Recipient("participant", case["id"]),
                    projection={
                        "positions": {
                            actor: dict(
                                cell=tuple(native["executed_position"]),
                                direction=struct.unpack_from(">b", payload, 20)[0],
                            )
                        }
                    },
                    proof_bytes=self.raw,
                    trusted_proof_sha256=hashlib.sha256(self.raw).hexdigest(),
                )
                self.assertTrue(result["qualified"], result)


if __name__ == "__main__":
    unittest.main()
