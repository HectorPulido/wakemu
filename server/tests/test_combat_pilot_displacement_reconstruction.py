"""Actual original native old/new displacement endpoint model acceptance."""
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


def bootstrap(fight, positions):
    admission = struct.pack(
        ">ibqqqihqqBb", fight, 2, 0, 0, 0, 0, 0, 0, 0, 1, len(positions)
    )
    placement = struct.pack(">ih", fight, len(positions))
    for actor, cell in positions.items():
        admission += struct.pack(">qbbb", actor, int(actor < 0), int(actor < 0), 0)
        placement += struct.pack(">qiih", actor, *cell)
    admission += b"\x00\x00\x00" + struct.pack(">i", 0)
    return ((12847, admission), (13652, placement + b"\x01"))


class ActualNativeDisplacementProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_PILOT_DISPLACEMENT_NATIVE_PROOF")
        if not configured:
            raise unittest.SkipTest(
                "Actual old/new displacement original-consumer proof not configured"
            )
        cls.root = Path(configured)
        cls.raw = (cls.root / "proof.json").read_bytes()
        cls.proof = json.loads(cls.raw)
        if cls.proof.get("complete") is not True:
            raise AssertionError("Native logical displacement verification incomplete")

    def arguments(self, index=0):
        row = self.proof["cases"][index]
        payload = (self.root / f"displacement-{index}.bin").read_bytes()
        fight = struct.unpack_from(">i", payload)[0]
        origins = {
            int(actor): tuple(cell) for actor, cell in row["initial_positions"].items()
        }
        return dict(
            bootstrap=bootstrap(fight, origins),
            packet=(12613, payload),
            recipient=Recipient("participant", row["id"]),
            projection={
                int(actor): tuple(cell)
                for actor, cell in row["expected_positions"].items()
            },
            proof_bytes=self.raw,
            trusted_proof_sha256=hashlib.sha256(self.raw).hexdigest(),
        )

    def test_all_actual_old_new_callbacks_preserve_modeled_positions(self):
        self.assertEqual(len(self.proof["cases"]), 8)
        self.assertEqual(
            {row["native"]["family"] for row in self.proof["cases"]},
            {300, 301, 340, 422},
        )
        for index, row in enumerate(self.proof["cases"]):
            with self.subTest(case=row["id"]):
                result = verify_native_displacement_case(**self.arguments(index))
                self.assertTrue(result["qualified"], result)
                self.assertFalse(result["pending"])
                self.assertFalse(result["visual_script_qualified"])
                self.assertFalse(result["rendering_qualified"])
                self.assertFalse(result["live_delivery_qualified"])

    def test_changed_action_identity_cannot_reuse_other_native_callback(self):
        args = self.arguments()
        opcode, payload = args["packet"]
        args["packet"] = opcode, payload[:4] + struct.pack(">i", 999) + payload[8:]
        self.assertFalse(verify_native_displacement_case(**args)["qualified"])

    def test_changed_domain_endpoint_is_detected(self):
        args = self.arguments()
        actor = next(iter(args["projection"]))
        args["projection"][actor] = (99, 99, 0)
        result = verify_native_displacement_case(**args)
        self.assertFalse(result["qualified"])
        self.assertEqual(result["reasons"], ["permitted_position_projection_differs"])

    def test_unregistered_actor_or_wrong_fight_cannot_converge(self):
        for fight, origins in (
            (77, {999: (0, 0, 0)}),
            (999, {7: (0, 0, 0), -7: (4, 0, 0)}),
        ):
            with self.subTest(fight=fight, origins=origins):
                args = self.arguments()
                args["bootstrap"] = bootstrap(fight, origins)
                self.assertFalse(verify_native_displacement_case(**args)["qualified"])

    def test_native_receipt_requires_separate_trust_pin(self):
        args = self.arguments()
        args["trusted_proof_sha256"] = None
        self.assertFalse(verify_native_displacement_case(**args)["qualified"])


if __name__ == "__main__":
    unittest.main()
