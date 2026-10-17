"""Actual owned Pandawa native logical position and reciprocal-owner acceptance."""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_pilot_carry_reconstruction import verify_native_carry_lifecycle
from wakfu_server.combat_protocol_reconstruction import Recipient, decode_packet


class ActualNativeCarryLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_PILOT_CARRY_NATIVE_PROOF")
        if not configured:
            raise unittest.SkipTest(
                "Actual owned carry/throw native callback proof not configured"
            )
        cls.root = Path(configured)
        cls.raw = (cls.root / "proof.json").read_bytes()
        cls.proof = json.loads(cls.raw)
        if cls.proof.get("complete") is not True:
            raise AssertionError("Original owned carry/throw logical proof incomplete")

    def arguments(self, index=0):
        row = self.proof["cases"][index]
        packets = tuple(
            (12613, (self.root / f"{row['id']}-{stage}.bin").read_bytes())
            for stage in (0, 1)
        )
        return dict(
            packets=packets,
            recipient=Recipient("participant", row["id"]),
            initial_projection=row["expected"][0]["before"],
            projection=row["expected"][1]["after"],
            proof_bytes=self.raw,
            trusted_proof_sha256=hashlib.sha256(self.raw).hexdigest(),
        )

    def test_both_actual_owned_carry_throw_branches_converge(self):
        self.assertEqual(
            {row["id"] for row in self.proof["cases"]}, {"legacy", "pilot"}
        )
        for index, row in enumerate(self.proof["cases"]):
            with self.subTest(branch=row["id"]):
                args = self.arguments(index)
                self.assertEqual(
                    decode_packet(*args["packets"][0])["effect"]["family"], 334
                )
                throw = decode_packet(*args["packets"][1])["effect"]
                self.assertEqual(throw["family"], 333)
                self.assertIsNone(
                    throw["target"], "Actual native nullable target must remain absent"
                )
                result = verify_native_carry_lifecycle(**args)
                self.assertTrue(result["qualified"], result)
                self.assertFalse(result["pending"])
                self.assertFalse(result["rendering_qualified"])
                self.assertFalse(result["visual_parenting_qualified"])
                self.assertFalse(result["live_delivery_qualified"])

    def test_wrong_initial_reciprocal_owner_cannot_converge(self):
        args = self.arguments()
        args["initial_projection"] = copy.deepcopy(args["initial_projection"])
        args["initial_projection"]["relations"]["7"]["carried"] = 999
        self.assertFalse(verify_native_carry_lifecycle(**args)["qualified"])

    def test_changed_action_or_reordered_packets_cannot_reuse_callbacks(self):
        args = self.arguments()
        first, second = args["packets"]
        payload = first[1]
        args["packets"] = (
            (12613, payload[:4] + struct.pack(">i", 999) + payload[8:]),
            second,
        )
        self.assertFalse(verify_native_carry_lifecycle(**args)["qualified"])
        args = self.arguments()
        args["packets"] = tuple(reversed(args["packets"]))
        self.assertFalse(verify_native_carry_lifecycle(**args)["qualified"])

    def test_retained_owner_after_throw_is_detected(self):
        args = self.arguments()
        args["projection"] = copy.deepcopy(args["projection"])
        args["projection"]["relations"]["-7"]["carrier"] = 7
        self.assertFalse(verify_native_carry_lifecycle(**args)["qualified"])

    def test_native_receipt_cannot_self_qualify_without_trust_pin(self):
        args = self.arguments()
        args["trusted_proof_sha256"] = None
        self.assertFalse(verify_native_carry_lifecycle(**args)["qualified"])


if __name__ == "__main__":
    unittest.main()
