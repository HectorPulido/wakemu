"""Independent native fixture comparisons and sequence/lifecycle negatives.

Generate the untouched-JAR corpus with verify_combat_reconstruction_native.py,
then set WAKFU_NATIVE_PROTOCOL_FIXTURES to its new private output directory.
Absent native evidence is an explicit skipped integration class, never a pass.
Pure API/input checks below do not need the native installation.
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_protocol_reconstruction import (
    BlockCompletion,
    EffectContract,
    MalformedPacket,
    Recipient,
    TerminalCompletion,
    compare_permitted_projection,
    decode_packet,
    reconstruct_packets,
)


class ReconstructionInputTests(unittest.TestCase):
    def test_missing_bootstrap_and_unknown_opcode_cannot_converge(self):
        recipient = Recipient("participant", "session-one")
        result = reconstruct_packets([], [(65500, b"opaque")], recipient=recipient)
        self.assertEqual(
            {f.status for f in result.findings},
            {"incomplete_evidence", "unknown_coverage"},
        )
        self.assertFalse(
            compare_permitted_projection(
                result, recipient=recipient, projection={"entities": {}}
            )["matches"]
        )

    def test_malformed_packet_is_distinct_from_unsupported(self):
        with self.assertRaises(MalformedPacket):
            decode_packet(13624, b"short")
        self.assertEqual(decode_packet(65000, b"short")["kind"], "unsupported")

    def test_role_generation_and_missing_projection_are_not_defaulted(self):
        recipient = Recipient("participant", "old")
        result = reconstruct_packets([], [], recipient=recipient)
        for other, projection in (
            (Recipient("participant", "new"), {"entities": {}}),
            (Recipient("spectator", "old"), {"entities": {}}),
            (recipient, {}),
            (recipient, {"private_fight": {}}),
        ):
            with self.subTest(other=other, projection=projection), self.assertRaises(
                ValueError
            ):
                compare_permitted_projection(
                    result, recipient=other, projection=projection
                )

    def test_completion_contract_requires_bounded_explicit_identity(self):
        with self.assertRaises(ValueError):
            BlockCompletion(0, (1,), "not-a-proof-hash")
        with self.assertRaises(ValueError):
            EffectContract(999, True, False, "a" * 64)


class NativeReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_NATIVE_PROTOCOL_FIXTURES")
        if not configured:
            raise unittest.SkipTest("Independent native fixture receipt not configured")
        cls.root = Path(configured)
        raw = (cls.root / "native-proof.json").read_bytes()
        cls.receipt = json.loads(raw)
        if (
            cls.receipt.get("complete") is not True
            or cls.receipt.get("returncode") != 0
            or cls.receipt.get("instrumentation") != "none"
        ):
            raise AssertionError(
                "Native oracle did not complete without instrumentation"
            )
        cls.proof = hashlib.sha256(raw).hexdigest()
        for name, expected in cls.receipt["fixtures"].items():
            if hashlib.sha256((cls.root / name).read_bytes()).hexdigest() != expected:
                raise AssertionError("Native fixture hash mismatch: " + name)
        observations = (cls.root / "observations.json").read_bytes()
        if (
            hashlib.sha256(observations).hexdigest()
            != cls.receipt["observations_sha256"]
        ):
            raise AssertionError("Independent observations hash mismatch")
        cls.native = json.loads(observations)
        cls.recipient = Recipient("participant", "native-fixture-generation")

    def packet(self, filename):
        return (
            int(filename.split("-", 1)[0]),
            (self.root / (filename + ".bin")).read_bytes(),
        )

    def bootstrap(self):
        return [self.packet("12847"), self.packet("13652")]

    def witness(self, block, *actions):
        return BlockCompletion(block, tuple(actions), self.proof)

    def contracts(self, *, retained=True):
        state = self.native["state310"]
        area = self.native["area315"]["area315-keep0-retained1"]
        return {
            (state["generic_effect"], 310): EffectContract(
                310, True, False, self.proof
            ),
            (area["generic_effect"], 315): EffectContract(
                315, retained, False, self.proof
            ),
        }

    def reconstruct(
        self,
        updates,
        *,
        completions=(),
        contracts=None,
        bootstrap=None,
        terminal_completion=None
    ):
        return reconstruct_packets(
            self.bootstrap() if bootstrap is None else bootstrap,
            updates,
            recipient=self.recipient,
            effect_contracts=self.contracts() if contracts is None else contracts,
            completions=completions,
            terminal_completion=terminal_completion,
        )

    def test_bootstrap_and_movement_decode_agree_with_original_classes(self):
        roster = decode_packet(*self.packet("12847"))
        positions = decode_packet(*self.packet("13652"))
        movement = decode_packet(*self.packet("13624"))
        self.assertEqual(
            [a["id"] for a in roster["actors"]], self.native["bootstrap"]["actor_ids"]
        )
        self.assertEqual(roster["fight"], self.native["bootstrap"]["fight_id"])
        self.assertEqual(
            [list((actor, *cell)) for actor, cell in positions["positions"]],
            self.native["positions"]["positions"],
        )
        self.assertEqual(
            [list(point) for point in movement["path"]],
            self.native["movement"]["points"],
        )
        self.assertEqual(movement["actor"], self.native["movement"]["actor_id"])
        self.assertEqual(movement["mode"], 0)

    def test_received_movement_does_not_execute_at_fence_without_witness(self):
        packets = [self.packet("13624"), self.packet("13420")]
        result = self.reconstruct(packets)
        self.assertEqual(result.received.positions[22], (4, -3, 4))
        self.assertEqual(result.executed.positions[22]["cell"], (2, -3, 4))
        self.assertEqual(result.pending_blocks[0]["action_ids"], (7,))
        comparison = compare_permitted_projection(
            result,
            recipient=self.recipient,
            projection={"positions": result.executed.positions},
        )
        self.assertFalse(comparison["matches"])
        self.assertTrue(comparison["pending"])

    def test_empty_fences_do_not_create_native_execution_groups(self):
        result = self.reconstruct([self.packet("13420"), self.packet("13420")])
        self.assertFalse(result.pending_blocks)
        self.assertFalse(result.open_actions)
        self.assertFalse(result.findings)

    def test_supported_position_projection_changes_only_after_observed_completion(self):
        result = self.reconstruct(
            [self.packet("13624"), self.packet("13420")],
            completions=(self.witness(0, 7),),
        )
        expected = {
            22: dict(cell=(4, -3, 4), direction=1),
            -33: dict(cell=(5, -3, 4), direction=None),
        }
        self.assertEqual(result.executed.positions, expected)
        self.assertTrue(
            compare_permitted_projection(
                result, recipient=self.recipient, projection={"positions": expected}
            )["matches"]
        )
        changed = copy.deepcopy(expected)
        changed[22]["cell"] = (3, -3, 4)
        self.assertFalse(
            compare_permitted_projection(
                result, recipient=self.recipient, projection={"positions": changed}
            )["matches"]
        )

    def test_state310_native_registration_observation_and_owned_removal(self):
        native = self.native["state310"]
        decoded = decode_packet(*self.packet("12613-state310"))["effect"]
        self.assertEqual(
            (
                decoded["uid"],
                decoded["base_uid"],
                decoded["caster"],
                decoded["target"],
                decoded["state_id"],
                decoded["level"],
            ),
            (
                native["uid"],
                native["base_uid"],
                native["caster_id"],
                native["target_id"],
                native["state_reference"],
                native["state_level"],
            ),
        )
        application = [self.packet("12613-state310"), self.packet("13420")]
        installed = self.reconstruct(application, completions=(self.witness(0, 8),))
        self.assertEqual(
            len(installed.executed.states),
            native["native_outcomes"]["completion_registrations"],
        )
        observed = self.reconstruct(
            [self.packet("13497-state310"), self.packet("13420")],
            completions=(self.witness(0, 9),),
        )
        self.assertEqual(
            len(observed.executed.states),
            native["native_outcomes"]["observation_registrations"],
        )
        final = self.reconstruct(
            application + [self.packet("13560-state310"), self.packet("13420")],
            completions=(self.witness(0, 8), self.witness(1, 10)),
        )
        self.assertEqual(
            len(final.executed.states), native["native_outcomes"]["removal_remaining"]
        )
        self.assertFalse(final.findings)

    def test_actual_native_area_creation_and_retained_keep_removal(self):
        for keep in (0, 1):
            name = "area315-keep%d-retained1" % keep
            native = self.native["area315"][name]
            addition = self.packet("12613-" + name)
            parsed = decode_packet(*addition)["effect"]
            self.assertEqual(
                (parsed["area_uid"], parsed["prototype"], parsed["keep_after"]),
                (native["area_uid"], native["prototype"], native["keep"]),
            )
            installed = self.reconstruct(
                [addition, self.packet("13420")], completions=(self.witness(0, 11),)
            )
            self.assertIn(native["area_uid"], installed.executed.areas)
            removed = self.reconstruct(
                [
                    addition,
                    self.packet("13420"),
                    self.packet("13560-" + name),
                    self.packet("13420"),
                ],
                completions=(self.witness(0, 11), self.witness(1, 12)),
            )
            self.assertFalse(removed.findings)
            self.assertEqual(len(removed.executed.areas), native["native_remaining"])
            self.assertFalse(removed.executed.runners)

    def test_entity_removal_remains_deferred_as_required_by_native_consumer(self):
        packet = self.packet("12304")
        native = self.native["entity_removal"]
        self.assertEqual(
            decode_packet(*packet)["actors"], [(native["type"], native["actor_id"])]
        )
        result = self.reconstruct([packet])
        self.assertIn(native["actor_id"], result.executed.entities)
        self.assertIn(native["actor_id"], result.executed.positions)
        self.assertIn(22, result.executed.entities)
        self.assertEqual(result.deferred_removals, (-33,))
        self.assertFalse(result.findings)

    def test_native_normal_terminal_removes_membership_only_after_cleanup_witness(self):
        packet = self.packet("12238")
        native = self.native["terminal"]
        parsed = decode_packet(*packet)
        self.assertEqual(parsed["action"], native["action_id"])
        self.assertEqual(parsed["winners"], [22])
        self.assertEqual(parsed["losers"], [-33])
        pending = self.reconstruct([self.packet("12304"), packet])
        self.assertEqual(set(pending.executed.entities), {22, -33})
        self.assertEqual(pending.pending_terminal, parsed["action"])
        result = self.reconstruct(
            [self.packet("12304"), packet],
            terminal_completion=TerminalCompletion(parsed["action"], self.proof),
        )
        self.assertFalse(result.executed.entities)
        self.assertFalse(result.executed.positions)
        self.assertFalse(result.deferred_removals)
        self.assertTrue(
            compare_permitted_projection(
                result,
                recipient=self.recipient,
                projection={"entities": {}, "positions": {}},
            )["matches"]
        )
        # A real normal terminal cannot silently drain an unproved preceding
        # block; nor can a terminal witness be substituted for turn12925/13510.
        unresolved = self.reconstruct(
            [self.packet("13624"), self.packet("13420"), packet],
            terminal_completion=TerminalCompletion(parsed["action"], self.proof),
        )
        self.assertTrue(unresolved.executed.entities)
        self.assertTrue(unresolved.pending_blocks)

    def test_missing_birth_duplicate_action_and_early_later_completion_fail(self):
        without_birth = self.reconstruct(
            [self.packet("13624")], bootstrap=[self.packet("13652")]
        )
        self.assertTrue(
            any(f.status == "contradiction" for f in without_birth.findings)
        )
        duplicate = self.reconstruct(
            [self.packet("13624"), self.packet("13624"), self.packet("13420")]
        )
        self.assertTrue(
            any("Duplicate active" in f.relationship for f in duplicate.findings)
        )
        queued = self.reconstruct(
            [
                self.packet("13624"),
                self.packet("13420"),
                self.packet("12613-state310"),
                self.packet("13420"),
            ],
            completions=(self.witness(1, 8),),
        )
        self.assertFalse(queued.executed.states)
        self.assertEqual(len(queued.pending_blocks), 2)

    def test_wrong_completion_owner_missing_removal_and_unknown_contract_stay_explicit(
        self,
    ):
        add = self.packet("12613-state310")
        wrong_witness = self.reconstruct(
            [add, self.packet("13420")], completions=(self.witness(0, 99),)
        )
        self.assertTrue(
            any("witness" in f.relationship for f in wrong_witness.findings)
        )
        installed = self.reconstruct(
            [add, self.packet("13420")], completions=(self.witness(0, 8),)
        )
        self.assertFalse(
            compare_permitted_projection(
                installed, recipient=self.recipient, projection={"states": {}}
            )["matches"]
        )
        missing = self.reconstruct(
            [add, self.packet("13420")], completions=(self.witness(0, 8),), contracts={}
        )
        self.assertFalse(missing.executed.states)
        self.assertTrue(any(f.status == "unknown_coverage" for f in missing.findings))
        opcode, body = self.packet("13560-state310")
        wrong_owner = (opcode, body[:-16] + struct.pack(">qq", 22, 2345))
        failed = self.reconstruct(
            [add, self.packet("13420"), wrong_owner, self.packet("13420")],
            completions=(self.witness(0, 8), self.witness(1, 10)),
        )
        self.assertIn(2345, failed.executed.states)
        self.assertTrue(any("owner" in f.relationship for f in failed.findings))

    def test_unsupported_mode_and_partial_path_cannot_claim_convergence(self):
        opcode, body = self.packet("13624")
        for altered in (body[:21] + b"\x7f" + body[22:], body + b"\x00"):
            result = self.reconstruct(
                [(opcode, altered), self.packet("13420")],
                completions=(self.witness(0, 7),),
            )
            self.assertEqual(result.executed.positions[22]["cell"], (2, -3, 4))
            self.assertTrue(
                any(f.status == "unknown_coverage" for f in result.findings)
            )

    def test_unmodeled_effect_can_not_qualify_unaffected_looking_position_projection(
        self,
    ):
        opcode, body = self.packet("12613-state310")
        # Family300 is native push: the envelope still decodes, but it cannot
        # be silently ignored while declaring positional convergence.
        unknown = (opcode, body[:13] + struct.pack(">i", 300) + body[17:])
        result = self.reconstruct(
            [unknown, self.packet("13420")], completions=(self.witness(0, 8),)
        )
        self.assertFalse(
            compare_permitted_projection(
                result,
                recipient=self.recipient,
                projection={"positions": result.executed.positions},
            )["matches"]
        )

    def test_inputs_are_preserved_and_truncated_payload_does_not_partially_register(
        self,
    ):
        source = self.bootstrap()
        original = copy.deepcopy(source)
        opcode, payload = self.packet("12613-state310")
        result = self.reconstruct([(opcode, payload[:-1])], bootstrap=source)
        self.assertEqual(source, original)
        self.assertFalse(result.executed.states)
        self.assertTrue(any(f.status == "malformed" for f in result.findings))


if __name__ == "__main__":
    unittest.main()
