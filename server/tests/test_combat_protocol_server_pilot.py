"""Actual production bytes -> original consumer -> independent recipient model.

The corpus is produced by combat_protocol_server_pilot.py and verified by an
untouched-JAR Java process. No server serializer is used to decode or determine
native expected behavior. Native callback identities supply completion facts.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest

from wakfu_server.combat_protocol_reconstruction import Recipient
from wakfu_server.combat_protocol_replay_verification import (
    SCHEMA,
    attach_replay_reconstruction,
    load_native_reconstruction_sidecar,
    stream_digest,
    verify_replay_projection,
)


class OptionalReconstructionTests(unittest.TestCase):
    def test_absent_native_evidence_preserves_existing_replay_result(self):
        original = dict(
            operation_matches=True, status="accepted", actual_sha256="historical"
        )
        before = copy.deepcopy(original)
        result = attach_replay_reconstruction(
            original,
            bootstrap=[],
            packets=[],
            recipient=Recipient("participant", "one"),
            permitted_projection={"entities": {}},
        )
        self.assertEqual(original, before)
        self.assertTrue(result["operation_matches"])
        self.assertEqual(result["status"], "accepted")
        self.assertFalse(result["protocol_reconstruction"]["qualified"])
        self.assertEqual(
            result["protocol_reconstruction"]["reasons"],
            ["native_reconstruction_evidence_missing"],
        )


class ServerProtocolPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_SERVER_PROTOCOL_PILOT")
        if not configured:
            raise unittest.SkipTest(
                "Original-consumer server-byte pilot not configured"
            )
        cls.root = Path(configured)
        cls.raw_proof = (cls.root / "server-native-proof.json").read_bytes()
        cls.proof = json.loads(cls.raw_proof)
        if (
            cls.proof.get("complete") is not True
            or cls.proof.get("instrumentation") != "none"
        ):
            raise AssertionError("Original-consumer pilot did not complete")
        cls.native_raw = (cls.root / "server-native-observations.json").read_bytes()
        cls.native = json.loads(cls.native_raw)
        cls.domain = json.loads((cls.root / "server-projection.json").read_text())
        cls.metadata = json.loads((cls.root / "server-pilot.json").read_text())
        if (
            hashlib.sha256(
                (cls.root / "server-projection.json").read_bytes()
            ).hexdigest()
            != cls.metadata["projection_sha256"]
        ):
            raise AssertionError("Explicit server projection input changed")
        if (
            hashlib.sha256((cls.root / "server-pilot.json").read_bytes()).hexdigest()
            != cls.proof["server_metadata_sha256"]
        ):
            raise AssertionError("Server producer metadata differs from native proof")
        cls.trusted_digest = hashlib.sha256(cls.raw_proof).hexdigest()
        cls.recipient = Recipient(**cls.domain["recipient"])

    def packet(self, name):
        return (
            self.metadata["packets"][name]["opcode"],
            (self.root / (name + ".bin")).read_bytes(),
        )

    def bootstrap(self):
        return [self.packet("12847"), self.packet("13652")]

    def projection(self, name):
        values = copy.deepcopy(self.domain[name])
        for row in values.values():
            if "cell" in row:
                row["cell"] = tuple(row["cell"])
        return {int(key): value for key, value in values.items()}

    def evidence(self, packets, *, completions=()):
        contracts = []
        for section in ("state310", "area315"):
            native = self.native[section]["native_contract"]
            contracts.append(
                dict(
                    definition=native["generic_effect"],
                    family=native["family"],
                    retained=native["retained_before_application"],
                    observation_registers=native["observation_registers"],
                )
            )
        return dict(
            schema=SCHEMA,
            recipient=self.domain["recipient"],
            stream_sha256=stream_digest(self.bootstrap(), packets),
            proof_bytes=self.raw_proof,
            observations_bytes=self.native_raw,
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

    def verify(
        self, packets, projection, *, evidence=None, completions=(), bootstrap=None
    ):
        return verify_replay_projection(
            bootstrap=self.bootstrap() if bootstrap is None else bootstrap,
            packets=packets,
            recipient=self.recipient,
            permitted_projection=projection,
            native_evidence=self.evidence(packets, completions=completions)
            if evidence is None
            else evidence,
            trusted_native_proof_sha256=self.trusted_digest,
        )

    def test_actual_server_placement_matches_explicit_permitted_domain_projection(self):
        self.assertEqual(
            self.native["bootstrap"]["actor_ids"],
            list(map(int, self.domain["entities"])),
        )
        result = self.verify(
            [],
            {
                "entities": self.projection("entities"),
                "positions": self.projection("initial_positions"),
            },
        )
        self.assertTrue(result["qualified"], result)
        self.assertFalse(result["client_receipt_qualified"])
        self.assertFalse(result["rendering_qualified"])

    def test_server_state_and_area_lifecycles_converge_at_actual_native_queue_callbacks(
        self,
    ):
        for kind, component, installed, removed in (
            ("state310", "states", "installed_states", "removed_states"),
            ("area315", "areas", "installed_areas", "removed_areas"),
        ):
            native = self.native[kind]
            add = [self.packet("12613-" + kind), self.packet("13420")]
            applied = self.verify(
                add,
                {component: self.projection(installed)},
                completions=((native["application_action"],),),
            )
            self.assertTrue(applied["qualified"], applied)
            final = add + [self.packet("13560-" + kind), self.packet("13420")]
            result = self.verify(
                final,
                {component: self.projection(removed)},
                completions=(
                    (native["application_action"],),
                    (native["removal_action"],),
                ),
            )
            self.assertTrue(result["qualified"], result)
            self.assertEqual(native["remaining"], 0)

    def test_missing_server_removal_disagrees_with_explicit_final_domain_projection(
        self,
    ):
        packets = [self.packet("12613-area315"), self.packet("13420")]
        native = self.native["area315"]
        result = self.verify(
            packets,
            {"areas": self.projection("removed_areas")},
            completions=((native["application_action"],),),
        )
        self.assertFalse(result["qualified"])
        self.assertEqual(result["differences"], ["areas"])

    def test_server_movement_without_native_animation_completion_remains_unqualified(
        self,
    ):
        packets = [self.packet("13624"), self.packet("13420")]
        result = self.verify(
            packets, {"positions": self.projection("movement_positions")}
        )
        self.assertFalse(result["qualified"])
        self.assertTrue(result["pending"])
        forged = self.evidence(packets, completions=((7,),))
        result = self.verify(
            packets,
            {"positions": self.projection("movement_positions")},
            evidence=forged,
        )
        self.assertFalse(result["qualified"])
        self.assertIn("absent from original native callbacks", result["reasons"][0])

    def test_changed_packets_native_facts_and_dispatch_ack_do_not_qualify(self):
        packets = [self.packet("12613-state310"), self.packet("13420")]
        native = self.native["state310"]
        evidence = self.evidence(
            packets, completions=((native["application_action"],),)
        )
        changed = copy.deepcopy(evidence)
        changed["effect_contracts"][0]["retained"] = False
        result = self.verify(
            packets, {"states": self.projection("installed_states")}, evidence=changed
        )
        self.assertFalse(result["qualified"])
        self.assertIn("not established", result["reasons"][0])
        changed = copy.deepcopy(evidence)
        changed["block_completions"][0]["source"] = "dispatch-returned"
        result = self.verify(
            packets, {"states": self.projection("installed_states")}, evidence=changed
        )
        self.assertFalse(result["qualified"])
        self.assertIn("not native execution completion", result["reasons"][0])
        opcode, body = packets[0]
        altered = [(opcode, body[:-1] + bytes([body[-1] ^ 1])), packets[1]]
        result = self.verify(
            altered, {"states": self.projection("installed_states")}, evidence=evidence
        )
        self.assertFalse(result["qualified"])
        self.assertIn("stream differs", result["reasons"][0])

    def test_actual_unsupported_recovery_bootstrap_and_unknown_frames_are_not_suppressed(
        self,
    ):
        # Actual recovery_packet output has a native cvn envelope proof, but
        # this reconstruction slice has no full12053/bootstrap state contract.
        initial = [self.packet("12053-recovery"), self.packet("13652")]
        evidence = self.evidence([])
        evidence["stream_sha256"] = stream_digest(initial, [])
        result = self.verify(
            [],
            {"entities": self.projection("entities")},
            evidence=evidence,
            bootstrap=initial,
        )
        self.assertFalse(result["qualified"])
        self.assertTrue(
            any("12053" in finding["relationship"] for finding in result["findings"])
        )
        packets = [(65000, b"unmodeled")]
        result = self.verify(packets, {"entities": self.projection("entities")})
        self.assertFalse(result["qualified"])
        self.assertIn("not consumed", result["reasons"][0])

    def test_no_self_qualification_unpinned_proof_or_mixed_recipient_generation(self):
        evidence = self.evidence([])
        result = verify_replay_projection(
            bootstrap=self.bootstrap(),
            packets=[],
            recipient=self.recipient,
            permitted_projection={"entities": self.projection("entities")},
            native_evidence=evidence,
        )
        self.assertFalse(result["qualified"])
        self.assertIn("not independently pinned", result["reasons"][0])
        changed = copy.deepcopy(evidence)
        changed["recipient"]["generation"] = "another-session"
        result = self.verify(
            [], {"entities": self.projection("entities")}, evidence=changed
        )
        self.assertFalse(result["qualified"])
        self.assertIn("generation differs", result["reasons"][0])

    def test_sidecar_api_attaches_verified_component_without_changing_replay_status(
        self,
    ):
        evidence = self.evidence([])
        descriptor = {
            key: value
            for key, value in evidence.items()
            if key not in ("proof_bytes", "observations_bytes")
        }
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "server-native-proof.json").write_bytes(self.raw_proof)
            (root / "server-native-observations.json").write_bytes(self.native_raw)
            path = root / "reconstruction-sidecar.json"
            path.write_text(json.dumps(descriptor))
            loaded = load_native_reconstruction_sidecar(path)
            original = dict(status="accepted", operation_matches=True)
            result = attach_replay_reconstruction(
                original,
                bootstrap=self.bootstrap(),
                packets=[],
                recipient=self.recipient,
                permitted_projection={"entities": self.projection("entities")},
                native_evidence=loaded,
                trusted_native_proof_sha256=self.trusted_digest,
            )
        self.assertEqual(original, dict(status="accepted", operation_matches=True))
        self.assertTrue(result["protocol_reconstruction"]["qualified"], result)
        self.assertEqual(result["status"], "accepted")


if __name__ == "__main__":
    unittest.main()
