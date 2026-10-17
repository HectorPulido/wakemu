"""Actual original native selected area/state owned callback acceptance."""
import copy
import hashlib
import json
import os
from pathlib import Path
import unittest

from wakfu_server.combat_pilot_area_reconstruction import verify_native_area_lifecycle
from wakfu_server.combat_protocol_reconstruction import Recipient


class ActualNativeAreaLifecycleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_PILOT_AREA_NATIVE_PROOF")
        if not configured:
            raise unittest.SkipTest(
                "Actual owned native lifecycle proof not configured"
            )
        cls.root = Path(configured)
        cls.raw = (cls.root / "proof.json").read_bytes()
        cls.proof = json.loads(cls.raw)
        if cls.proof.get("complete") is not True:
            raise AssertionError("Original native lifecycle callback proof incomplete")

    def arguments(self, index=0):
        record = self.proof["cases"][index]
        directory = self.root / f"case-{index}"
        packets = tuple(
            (int(line.split(" ")[0]), (directory / line.split(" ")[1]).read_bytes())
            for line in (directory / "stream.txt").read_text().splitlines()
        )
        return dict(
            packets=packets,
            actor_ids=record["actor_ids"],
            recipient=Recipient("participant", record["id"]),
            projection=record["expected_projection"],
            proof_bytes=self.raw,
            trusted_proof_sha256=hashlib.sha256(self.raw).hexdigest(),
        )

    def test_all_actual_old_new_state_and_area_callbacks_converge(self):
        self.assertGreaterEqual(len(self.proof["cases"]), 2)
        families = {
            stage["family"]
            for row in self.proof["cases"]
            for stage in row["native"]["stages"]
        }
        self.assertIn(310, families)
        self.assertTrue(families.intersection((308, 315)))
        for index, record in enumerate(self.proof["cases"]):
            with self.subTest(case=record["id"]):
                result = verify_native_area_lifecycle(**self.arguments(index))
                self.assertTrue(result["qualified"], result)
                self.assertFalse(result["pending"])
                self.assertFalse(result["rendering_qualified"])
                self.assertFalse(result["visual_script_qualified"])
                self.assertFalse(result["live_delivery_qualified"])

    def test_real_area_pv_owns_state_until_native_area_unregisters(self):
        owners = []
        for index, record in enumerate(self.proof["cases"]):
            for stage in record["native"]["stages"]:
                for state in stage["after"]["states"].values():
                    if str(state["owner"]) in stage["after"]["areas"]:
                        owners.append(index)
        self.assertTrue(owners, "Need actual state owned by native area PV")
        for index in owners:
            result = verify_native_area_lifecycle(**self.arguments(index))
            self.assertTrue(result["qualified"], result)
            self.assertEqual(result["executed"], {"states": {}, "areas": {}})

    def test_missing_or_reordered_retirement_cannot_reuse_native_evidence(self):
        for mutate in (
            lambda packets: packets[:-1],
            lambda packets: tuple(reversed(packets)),
        ):
            args = self.arguments()
            args["packets"] = mutate(args["packets"])
            self.assertFalse(verify_native_area_lifecycle(**args)["qualified"])

    def test_unregistered_caster_and_wrong_domain_projection_are_rejected(self):
        args = self.arguments()
        args["actor_ids"] = []
        self.assertFalse(verify_native_area_lifecycle(**args)["qualified"])
        args = self.arguments()
        args["projection"] = copy.deepcopy(args["projection"])
        args["projection"]["areas"]["999"] = dict(prototype=1, cell=[0, 0, 0])
        self.assertFalse(verify_native_area_lifecycle(**args)["qualified"])

    def test_native_receipt_cannot_self_qualify_without_trust_pin(self):
        args = self.arguments()
        args["trusted_proof_sha256"] = None
        self.assertFalse(verify_native_area_lifecycle(**args)["qualified"])


if __name__ == "__main__":
    unittest.main()
