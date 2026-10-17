"""Synthetic byte regressions; these fixtures do not attest native completion."""
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_pilot_protocol_comparison import (
    compare_recipient_deliveries,
    decode_recipient_delivery,
)
from wakfu_server.combat_protocol_reconstruction import Recipient
from wakfu_server.combat_protocol_replay_verification import SCHEMA, stream_digest


def bootstrap():
    admission = (
        struct.pack(">ibqqq", 99, 2, 0, 0, 0)
        + struct.pack(">ihqqBb", 0, 0, 22, -33, 1, 2)
        + struct.pack(">qbbbqbbb", 22, 0, 0, 0, -33, 1, 1, 0)
        + b"\x00\x00\x00"
        + struct.pack(">i", 0)
    )
    placement = struct.pack(">ih", 99, 2) + struct.pack(
        ">qiihqiihB", 22, 2, -3, 4, -33, 5, -3, 4, 1
    )
    return ((12847, admission), (13652, placement))


def movement(action=7, actor=22, end=4):
    return (
        13624,
        struct.pack(">iiiqbb", 99, action, -1, actor, 1, 0)
        + struct.pack(">iihiih", 2, -3, 4, end, -3, 4),
    )


def varint(value):
    result = bytearray()
    while value > 127:
        result.append((value & 127) | 128)
        value >>= 7
    result.append(value)
    return bytes(result)


def scalar(field, value):
    return varint(field << 3) + varint(value)


def nested(field, body):
    return varint((field << 3) | 2) + varint(len(body)) + body


def effect_pair(family, *, uid=2345, area=7002, removal_target=22):
    additional = (
        scalar(10, (3442 << 16) | 1) + scalar(13, uid)
        if family == 310
        else scalar(21, area) + scalar(14, 1)
    )
    effect = (
        scalar(1, uid)
        + scalar(2, 1234)
        + scalar(3, 123)
        + scalar(4, (3442 << 16) | 1 if family == 310 else 1474)
        + scalar(6, 22)
        + scalar(7, 22)
        + nested(8, additional)
        + nested(11, scalar(1, 1))
    )
    if family != 310:
        effect += nested(5, scalar(1, 2) + scalar(2, 3) + scalar(3, 4))
    application = (
        12613,
        struct.pack(">iiiBih", 99, 8, -1, 0, family, len(effect)) + effect,
    )
    removal = (
        13560,
        struct.pack(">iiiih", 99, 9, -1, family, len(effect))
        + effect
        + struct.pack(">qq", removal_target, uid),
    )
    return application, removal


class PilotProtocolComparisonTests(unittest.TestCase):
    recipient = Recipient("participant", "pilot-one")

    def compare(self, old, new, **kwargs):
        return compare_recipient_deliveries(
            recipient=self.recipient,
            old_bootstrap=bootstrap(),
            old_packets=old,
            new_bootstrap=bootstrap(),
            new_packets=new,
            old_projection={"positions": {}},
            new_projection={"positions": {}},
            **kwargs
        )

    def test_equal_received_movement_cannot_claim_execution(self):
        packets = (movement(), (13420, struct.pack(">i", 99)))
        result = self.compare(packets, packets)
        self.assertTrue(result["packet_bytes_equal"])
        self.assertTrue(result["modeled_observations_equal"])
        self.assertFalse(result["execution_qualified"])
        self.assertEqual(result["old"]["received"]["positions"][22], (4, -3, 4))
        self.assertEqual(result["old"]["executed"]["positions"][22]["cell"], (2, -3, 4))
        self.assertEqual(
            result["old"]["queue"]["pending_blocks"][0]["action_ids"], (7,)
        )

    def test_action_identity_difference_survives_equal_destination(self):
        result = self.compare((movement(action=7),), (movement(action=8),))
        self.assertIn("decoded", result["differences"])
        self.assertIn("queue", result["differences"])
        self.assertEqual(result["old"]["received"], result["new"]["received"])

    def test_positional_difference_and_unknown_registration_are_detected(self):
        result = self.compare((movement(),), (movement(actor=999, end=3),))
        self.assertIn("received", result["differences"])
        self.assertIn("findings", result["differences"])
        self.assertTrue(
            any(item["status"] == "contradiction" for item in result["new"]["findings"])
        )

    def test_packet_order_preserved_even_with_same_final_destination(self):
        result = self.compare(
            (movement(action=7, end=3), movement(action=8)),
            (movement(action=8), movement(action=7, end=3)),
        )
        self.assertIn("decoded", result["differences"])
        self.assertIn("queue", result["differences"])

    def test_identical_unknown_effect_is_parity_not_supported_semantics(self):
        packets = ((65500, b"opaque-effect"),)
        result = self.compare(packets, packets)
        self.assertTrue(result["modeled_observations_equal"])
        self.assertFalse(result["execution_qualified"])
        self.assertEqual(result["old"]["findings"][0]["status"], "unknown_coverage")

    def test_bootstrap_boundary_is_part_of_identity(self):
        initial = bootstrap()
        left = decode_recipient_delivery(initial, (), recipient=self.recipient)
        right = decode_recipient_delivery(
            initial[:1], initial[1:], recipient=self.recipient
        )
        self.assertEqual(left["decoded"], right["decoded"])
        self.assertNotEqual(left["stream_sha256"], right["stream_sha256"])

    def test_area_registration_identity_and_removal_owner_are_not_normalized(self):
        old = effect_pair(315)
        for new in (effect_pair(315, area=7003), effect_pair(315, removal_target=999)):
            with self.subTest(new=new):
                result = self.compare(old, new)
                self.assertFalse(result["packet_bytes_equal"])
                self.assertIn("decoded", result["differences"])
                self.assertFalse(result["execution_qualified"])
        view = self.compare(old, old)["old"]
        self.assertEqual(view["decoded"][2]["effect"]["area_uid"], 7002)
        self.assertEqual(view["decoded"][3]["removal_target"], 22)

    def test_state_creation_removal_running_identity_is_preserved(self):
        result = self.compare(effect_pair(310), effect_pair(310, uid=2346))
        self.assertIn("decoded", result["differences"])
        self.assertEqual(result["old"]["decoded"][2]["effect"]["state_id"], 3442)
        self.assertEqual(result["old"]["decoded"][3]["effect"]["uid"], 2345)
        self.assertFalse(result["execution_qualified"])


class NativePilotProtocolComparisonTests(unittest.TestCase):
    """Recheck the existing exact original-consumer corpus; no new cast claim."""

    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_SERVER_PROTOCOL_PILOT")
        if not configured:
            raise unittest.SkipTest(
                "Original-consumer server-byte pilot not configured"
            )
        cls.root = Path(configured)
        cls.proof_raw = (cls.root / "server-native-proof.json").read_bytes()
        cls.observations_raw = (
            cls.root / "server-native-observations.json"
        ).read_bytes()
        cls.observations = json.loads(cls.observations_raw)
        cls.domain_raw = (cls.root / "server-projection.json").read_bytes()
        cls.domain = json.loads(cls.domain_raw)
        metadata_raw = (cls.root / "server-pilot.json").read_bytes()
        cls.metadata = json.loads(metadata_raw)
        cls.proof = json.loads(cls.proof_raw)
        if (
            hashlib.sha256(metadata_raw).hexdigest()
            != cls.proof["server_metadata_sha256"]
            or hashlib.sha256(cls.domain_raw).hexdigest()
            != cls.metadata["projection_sha256"]
        ):
            raise AssertionError("Native corpus producer/projection identity changed")
        cls.recipient = Recipient(**cls.domain["recipient"])

    def packet(self, name):
        return (
            self.metadata["packets"][name]["opcode"],
            (self.root / (name + ".bin")).read_bytes(),
        )

    def compare(self, component, packets, completions, projection):
        initial = (self.packet("12847"), self.packet("13652"))
        contracts = []
        for section in ("state310", "area315"):
            facts = self.observations[section]["native_contract"]
            contracts.append(
                dict(
                    definition=facts["generic_effect"],
                    family=facts["family"],
                    retained=facts["retained_before_application"],
                    observation_registers=facts["observation_registers"],
                )
            )
        evidence = dict(
            schema=SCHEMA,
            recipient=self.domain["recipient"],
            stream_sha256=stream_digest(initial, packets),
            proof_bytes=self.proof_raw,
            observations_bytes=self.observations_raw,
            effect_contracts=contracts,
            block_completions=[
                dict(
                    block_index=index,
                    action_ids=list(actions),
                    source="original-native-queue-callback",
                )
                for index, actions in enumerate(completions)
            ],
        )
        return compare_recipient_deliveries(
            recipient=self.recipient,
            old_bootstrap=initial,
            new_bootstrap=initial,
            old_packets=packets,
            new_packets=packets,
            old_projection={component: projection},
            new_projection={component: projection},
            old_native_evidence=evidence,
            new_native_evidence=evidence,
            trusted_native_proof_sha256=hashlib.sha256(self.proof_raw).hexdigest(),
        )

    def test_both_independent_area_and_state_removal_views_qualify(self):
        for kind, component in (("state310", "states"), ("area315", "areas")):
            with self.subTest(kind=kind):
                native = self.observations[kind]
                packets = (
                    self.packet("12613-" + kind),
                    self.packet("13420"),
                    self.packet("13560-" + kind),
                    self.packet("13420"),
                )
                result = self.compare(
                    component,
                    packets,
                    ((native["application_action"],), (native["removal_action"],)),
                    {},
                )
                self.assertTrue(result["execution_qualified"], result)
                self.assertTrue(result["modeled_observations_equal"])

    def test_real_movement_equality_cannot_invent_native_completion(self):
        packets = (self.packet("13624"), self.packet("13420"))
        positions = {
            int(uid): dict(cell=tuple(row["cell"]), direction=row["direction"])
            for uid, row in self.domain["movement_positions"].items()
        }
        result = self.compare("positions", packets, (), positions)
        self.assertTrue(result["packet_bytes_equal"])
        self.assertFalse(result["execution_qualified"])
        self.assertTrue(result["old_native_verification"]["pending"])


if __name__ == "__main__":
    unittest.main()
