"""Exact original-consumer endpoint proof for the inactive 3217 content pilot."""
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_pilot_displacement_reconstruction import (
    verify_native_displacement_case,
)
from wakfu_server.combat_protocol_reconstruction import Recipient


class ActualNewContentReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_PILOT_NEW_CONTENT_NATIVE_PROOF")
        if not configured:
            raise unittest.SkipTest(
                "Actual new-content original-consumer proof not configured"
            )
        cls.root = Path(configured)
        cls.raw = (cls.root / "proof.json").read_bytes()
        cls.proof = json.loads(cls.raw)
        if cls.proof.get("complete") is not True:
            raise AssertionError("New-content native endpoint proof incomplete")

    def arguments(self, index):
        row = self.proof["cases"][index]
        payload = (self.root / f"displacement-{index}.bin").read_bytes()
        fight = struct.unpack_from(">i", payload)[0]
        positions = {
            int(actor): tuple(cell) for actor, cell in row["initial_positions"].items()
        }
        admission = struct.pack(
            ">ibqqqihqqBb", fight, 2, 0, 0, 0, 0, 0, 0, 0, 1, len(positions)
        )
        placement = struct.pack(">ih", fight, len(positions))
        for actor, cell in positions.items():
            admission += struct.pack(">qbbb", actor, int(actor < 0), int(actor < 0), 0)
            placement += struct.pack(">qiih", actor, *cell)
        admission += b"\x00\x00\x00" + struct.pack(">i", 0)
        return dict(
            bootstrap=((12847, admission), (13652, placement + b"\x01")),
            packet=(12613, payload),
            recipient=Recipient("participant", row["id"]),
            projection={
                int(actor): tuple(cell)
                for actor, cell in row["expected_positions"].items()
            },
            proof_bytes=self.raw,
            trusted_proof_sha256=hashlib.sha256(self.raw).hexdigest(),
        )

    def test_both_actual_new_content_endpoints_are_independently_qualified(self):
        self.assertEqual(len(self.proof["cases"]), 2)
        for index, row in enumerate(self.proof["cases"]):
            with self.subTest(case=row["id"]):
                self.assertEqual(row["native"]["family"], 300)
                result = verify_native_displacement_case(**self.arguments(index))
                self.assertTrue(result["qualified"], result)
                self.assertFalse(result["rendering_qualified"])
                self.assertFalse(result["live_delivery_qualified"])

    def test_actual_new_content_identity_cannot_reuse_native_callback(self):
        args = self.arguments(0)
        opcode, payload = args["packet"]
        args["packet"] = opcode, payload[:4] + struct.pack(">i", 999) + payload[8:]
        self.assertFalse(verify_native_displacement_case(**args)["qualified"])

    def test_actual_new_content_wrong_endpoint_and_missing_pin_are_rejected(self):
        args = self.arguments(0)
        args["projection"][7] = (99, 99, 0)
        self.assertFalse(verify_native_displacement_case(**args)["qualified"])
        args = self.arguments(0)
        args["trusted_proof_sha256"] = None
        self.assertFalse(verify_native_displacement_case(**args)["qualified"])


if __name__ == "__main__":
    unittest.main()
