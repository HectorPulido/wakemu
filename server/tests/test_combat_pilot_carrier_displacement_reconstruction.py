"""Carrier endpoint model rejects incomplete relations and moves implicit partners."""
import unittest
import os
from unittest.mock import patch

from wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction import (
    modeled_carrier_displacement,
    normalize_view,
)


class CarrierDisplacementModelTests(unittest.TestCase):
    def setUp(self):
        self.before = dict(
            positions={"7": [0, 0, 0], "8": [0, 0, 0], "-7": [4, 0, 0]},
            relations={
                "7": dict(carrier=None, carried=8),
                "8": dict(carrier=7, carried=None),
                "-7": dict(carrier=None, carried=None),
            },
        )

    def model(self, endpoints):
        with patch(
            "wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction.decode_packet",
            return_value={"kind": "effect", "effect": {"family": 300}},
        ), patch(
            "wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction.modeled_displacement_positions",
            return_value=({"effect": {}}, endpoints),
        ):
            return modeled_carrier_displacement((12613, b""), self.before)[1]

    def test_carrier_displacement_moves_implicit_registered_partner(self):
        after = self.model({7: (2, 2, 0), 8: (0, 0, 0), -7: (4, 0, 0)})
        self.assertEqual(after["positions"]["8"], [2, 2, 0])
        self.assertEqual(after["relations"], self.before["relations"])
        self.assertEqual(self.before["positions"]["8"], [0, 0, 0])

    def test_swap_moves_partner_and_other_participant(self):
        after = self.model({7: (4, 0, 0), 8: (0, 0, 0), -7: (0, 0, 0)})
        self.assertEqual(
            after["positions"], {"7": [4, 0, 0], "8": [4, 0, 0], "-7": [0, 0, 0]}
        )

    def test_unrelated_displacement_preserves_pair(self):
        after = self.model({7: (0, 0, 0), 8: (0, 0, 0), -7: (5, 0, 0)})
        self.assertEqual(after["positions"]["8"], [0, 0, 0])

    def test_rejects_missing_reciprocal_partner(self):
        self.before["relations"]["8"]["carrier"] = None
        with self.assertRaisesRegex(ValueError, "reciprocal"):
            normalize_view(self.before)

    def test_rejects_non_colocated_pair(self):
        self.before["positions"]["8"] = [1, 0, 0]
        with self.assertRaisesRegex(ValueError, "colocated"):
            normalize_view(self.before)

    def test_rejects_unknown_relation_identity(self):
        self.before["relations"]["7"]["carried"] = 999
        with self.assertRaisesRegex(ValueError, "registered"):
            normalize_view(self.before)

    def test_rejects_direct_carried_displacement(self):
        with self.assertRaisesRegex(ValueError, "Direct carried"):
            self.model({7: (0, 0, 0), 8: (1, 0, 0), -7: (4, 0, 0)})

    def test_rejects_boolean_coordinate(self):
        self.before["positions"]["7"][0] = False
        with self.assertRaisesRegex(ValueError, "integer cell"):
            normalize_view(self.before)


class CarrierPinnedProofTests(unittest.TestCase):
    """Synthetic receipts test qualification guards, not native execution."""

    def setUp(self):
        CarrierDisplacementModelTests.setUp(self)
        self.decoded = dict(
            action=12,
            effect=dict(family=300, definition=358000, uid=200, caster=-7, target=7),
        )
        self.after = dict(
            positions={"7": [2, 0, 0], "8": [2, 0, 0], "-7": [4, 0, 0]},
            relations=self.before["relations"],
        )
        self.native = dict(
            completed_normally=True,
            queue_drained=True,
            action_id=12,
            native_completed_action_ids=[12],
            family=300,
            generic_effect=358000,
            uid=200,
            caster=-7,
            target=7,
            before=self.before,
            after=self.after,
        )
        import hashlib

        self.record = dict(
            id="synthetic",
            opcode=12613,
            payload_sha256=hashlib.sha256(b"packet").hexdigest(),
            initial=self.before,
            recipient=dict(
                schema="wakemu-combat-reproduction-state-v1",
                root="fixture-participant",
                nodes=[],
                services=[],
            ),
            expected=self.after,
            modeled=self.after,
            native=self.native,
            returncode=0,
            complete=True,
        )
        self.proof = dict(
            schema="wakemu-pilot-carrier-displacement-native-proof-v1",
            complete=True,
            source_stable=True,
            compile_returncode=0,
            instrumentation="none",
            classpath={"client/lib/wakfu-client.jar": "synthetic"},
            bdata={"binary": "synthetic"},
            source={
                "sniffer/java/VerifyPilotCarrierDisplacementQueue.java": "synthetic"
            },
            cases=[self.record],
        )

    def qualify(self, **changes):
        import hashlib
        import json
        from wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction import (
            verify_native_carrier_displacement_case,
        )

        raw = json.dumps(self.proof).encode()
        args = dict(
            packet=(12613, b"packet"),
            before=self.before,
            projection=self.after,
            recipient="fixture-participant",
            proof_bytes=raw,
            trusted_proof_sha256=hashlib.sha256(raw).hexdigest(),
        )
        args.update(changes)
        with patch(
            "wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction.modeled_carrier_displacement",
            return_value=(self.decoded, self.after),
        ):
            return verify_native_carrier_displacement_case(**args)

    def test_synthetic_pinned_exact_callback_qualifies_only_logical_scope(self):
        result = self.qualify()
        self.assertTrue(result["qualified"], result)
        self.assertFalse(result["live_delivery_qualified"])
        self.assertFalse(result["rendering_qualified"])

    def test_unpinned_proof_rejected(self):
        self.assertFalse(self.qualify(trusted_proof_sha256="0" * 64)["qualified"])

    def test_other_recipient_rejected(self):
        self.assertFalse(self.qualify(recipient="other")["qualified"])

    def test_false_exit_code_rejected(self):
        self.record["returncode"] = False
        self.assertFalse(self.qualify()["qualified"])

    def test_wrong_owner_rejected(self):
        self.native["caster"] = 999
        self.assertFalse(self.qualify()["qualified"])

    def test_wrong_action_rejected(self):
        self.native["action_id"] = 99
        self.assertFalse(self.qualify()["qualified"])

    def test_changed_packet_bytes_rejected(self):
        self.assertFalse(self.qualify(packet=(12613, b"changed"))["qualified"])

    def test_wrong_effect_uid_rejected(self):
        self.native["uid"] = 99
        self.assertFalse(self.qualify()["qualified"])

    def test_missing_completion_rejected(self):
        self.native["native_completed_action_ids"] = []
        self.assertFalse(self.qualify()["qualified"])

    def test_undrained_queue_rejected(self):
        self.native["queue_drained"] = False
        self.assertFalse(self.qualify()["qualified"])

    def test_original_partner_position_mismatch_rejected(self):
        from copy import deepcopy

        self.native["after"] = deepcopy(self.after)
        self.native["after"]["positions"]["8"] = [1, 0, 0]
        self.assertFalse(self.qualify()["qualified"])

    def test_projection_relation_mismatch_rejected(self):
        from copy import deepcopy

        projection = deepcopy(self.after)
        projection["relations"]["7"]["carried"] = None
        projection["relations"]["8"]["carrier"] = None
        self.assertFalse(self.qualify(projection=projection)["qualified"])

    def test_incomplete_receipt_rejected(self):
        self.proof["complete"] = False
        self.assertFalse(self.qualify()["qualified"])


class CasterTeleportModelTests(unittest.TestCase):
    def setUp(self):
        CarrierDisplacementModelTests.setUp(self)

    def test_real_family302_bytes_move_caster_and_partner(self):
        # Independent fixed wire vector; no server serializer or native-proof
        # claim. Original native execution is qualified separately.
        packet = bytes.fromhex(
            "0000004d00000001ffffffff000000012e001d08c80110c80118ecaa15200030073807420b7a06080210021800880201"
        )
        decoded, after = modeled_carrier_displacement((12613, packet), self.before)
        self.assertEqual(decoded["effect"]["family"], 302)
        self.assertEqual(after["positions"]["7"], [2, 2, 0])
        self.assertEqual(after["positions"]["8"], [2, 2, 0])


@unittest.skipUnless(
    os.environ.get("WAKFU_PILOT_CARRIER_NATIVE_PROOF"),
    "Explicit actual native carrier proof required",
)
class ActualCarrierPinnedProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import hashlib
        import json
        from pathlib import Path

        cls.path = Path(os.environ["WAKFU_PILOT_CARRIER_NATIVE_PROOF"])
        cls.raw = cls.path.read_bytes()
        cls.trusted = hashlib.sha256(cls.raw).hexdigest()
        cls.proof = json.loads(cls.raw)
        if len(cls.proof["cases"]) != 6:
            raise AssertionError("Actual three-case old/new corpus required")
        cls.records = [
            (row, (cls.path.parent / f"case-{index}.bin").read_bytes())
            for index, row in enumerate(cls.proof["cases"])
        ]

    def qualify(self, row, payload, **changes):
        from wakfu_server.combat.combat_pilot_carrier_displacement_reconstruction import (
            _recipient_label,
            verify_native_carrier_displacement_case,
        )

        args = dict(
            packet=(12613, payload),
            before=row["initial"],
            projection=row["expected"],
            recipient=_recipient_label(row["recipient"]),
            proof_bytes=self.raw,
            trusted_proof_sha256=self.trusted,
        )
        args.update(changes)
        return verify_native_carrier_displacement_case(**args)

    def test_all_actual_original_callbacks_qualify(self):
        families = set()
        for row, payload in self.records:
            with self.subTest(case=row["id"]):
                result = self.qualify(row, payload)
                self.assertTrue(result["qualified"], result)
                self.assertFalse(result["live_delivery_qualified"])
                self.assertFalse(result["rendering_qualified"])
                families.add(row["native"]["family"])
        self.assertEqual(families, {300, 302, 422})

    def test_actual_changed_action_bytes_never_qualify(self):
        for row, payload in self.records:
            with self.subTest(case=row["id"]):
                changed = bytearray(payload)
                changed[7] ^= 1
                self.assertFalse(self.qualify(row, bytes(changed))["qualified"])

    def test_actual_changed_partner_projection_never_qualifies(self):
        from copy import deepcopy

        for row, payload in self.records:
            with self.subTest(case=row["id"]):
                projection = deepcopy(row["expected"])
                carrier = next(
                    actor
                    for actor, rel in projection["relations"].items()
                    if rel["carried"] is not None
                )
                partner = str(projection["relations"][carrier]["carried"])
                projection["positions"][partner][0] += 1
                self.assertFalse(
                    self.qualify(row, payload, projection=projection)["qualified"]
                )

    def test_actual_other_recipient_never_qualifies(self):
        for row, payload in self.records:
            with self.subTest(case=row["id"]):
                self.assertFalse(
                    self.qualify(row, payload, recipient="other-recipient")["qualified"]
                )


if __name__ == "__main__":
    unittest.main()
