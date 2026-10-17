"""Original copied-descriptor oracle; does not accredit a complete1002 cast."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import unittest

from wakfu_server.combat_core_reconstruction import UnknownCoreLayout
from wakfu_server.combat_core_reconstruction_copy import (
    NativeCopyContract,
    decode_copy_descriptor,
    decode_copy_running_effect,
)
from wakfu_server.combat_protocol_reconstruction import MalformedPacket


class CopyReconstructionInputTests(unittest.TestCase):
    def test_unknown_native_descriptor_policy_is_not_defaulted(self):
        with self.assertRaises(UnknownCoreLayout):
            decode_copy_descriptor(b"", contract=None)
        with self.assertRaises(ValueError):
            NativeCopyContract(False, "not-an-independent-hash")


class NativeCopyReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_NATIVE_COPY_FIXTURES")
        if not configured:
            raise unittest.SkipTest("Original copied descriptor receipt not configured")
        cls.root = Path(configured)
        raw = (cls.root / "native-proof.json").read_bytes()
        receipt = json.loads(raw)
        if not (
            receipt.get("complete") is True
            and receipt.get("returncode") == 0
            and receipt.get("source_stable") is True
            and receipt.get("instrumentation") == "none"
        ):
            raise AssertionError("Incomplete original copied descriptor oracle")
        for name, digest in receipt["fixtures"].items():
            if hashlib.sha256((cls.root / name).read_bytes()).hexdigest() != digest:
                raise AssertionError("Changed native copy fixture")
        observed = (cls.root / "observations.json").read_bytes()
        if hashlib.sha256(observed).hexdigest() != receipt["observations_sha256"]:
            raise AssertionError("Changed native copy observations")
        cls.observed = json.loads(observed)
        cls.contract = NativeCopyContract(
            cls.observed["include_levels"], hashlib.sha256(raw).hexdigest()
        )
        cls.raw = (cls.root / "copy-descriptor.bin").read_bytes()

    def test_independent_book_owner_and_constructor_identity_match_original_native_codec(
        self,
    ):
        value = decode_copy_descriptor(self.raw, contract=self.contract)
        self.assertEqual(value["reference"], self.observed["reference"])
        self.assertEqual(value["descriptor_actor"], self.observed["constructor_actor"])
        self.assertEqual(value["owner"], self.observed["owner"])
        self.assertEqual(
            value["book"],
            [
                dict(
                    uid=self.observed["book_uid"],
                    reference=self.observed["book_reference"],
                    level=self.observed["book_level"],
                )
            ],
        )
        self.assertIsNone(value["level_trailer"])
        self.assertEqual(
            value["characteristics"],
            [dict(id=1, current=140, minimum=330, maximum=0, percentage=10000)],
        )

    def test_real_production_payload_preserves_generated_actor_separate_from_constructor_and_book(
        self,
    ):
        from test_combat_character_copy_codec import CharacterCopyCodecTests
        from wakfu_server.combat_character_copy_codec import character_copy_payload

        descriptor = replace(
            CharacterCopyCodecTests().descriptor(), reference=2382, actor_id=-1
        )
        payload = character_copy_payload(
            descriptor=descriptor,
            include_levels=False,
            uid=20,
            base_uid=20,
            effect_reference=413075,
            caster_id=7,
            cell=(1, 2, 0),
            timing_payload=b"",
            actual_actor_id=295,
        )
        value = decode_copy_running_effect(payload, contract=self.contract)
        self.assertEqual(
            (value["actor"], value["effect_uid"], value["caster"]), (295, 20, 7)
        )
        self.assertEqual(
            value["descriptor"],
            decode_copy_descriptor(self.raw, contract=self.contract),
        )
        self.assertNotEqual(value["actor"], value["descriptor"]["descriptor_actor"])
        self.assertNotEqual(value["actor"], value["descriptor"]["book"][0]["uid"])

    def test_trailer_policy_and_unmodeled_extension_fail_closed(self):
        with self.assertRaises(MalformedPacket):
            decode_copy_descriptor(self.raw + b"\x00", contract=self.contract)
        with self.assertRaises(MalformedPacket):
            decode_copy_descriptor(
                self.raw,
                contract=NativeCopyContract(True, self.contract.evidence_sha256),
            )
