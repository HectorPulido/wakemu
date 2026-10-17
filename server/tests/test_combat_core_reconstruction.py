"""Independent original-native core fixtures and real snapshot producer checks."""
import ast
import hashlib
import json
import os
from pathlib import Path
import struct
import unittest

from wakfu_server.combat_core_reconstruction import (
    UnknownCoreLayout,
    compare_core_view,
    decode_core_packet,
    decode_timeline,
    reconstruct_core,
)
from wakfu_server.combat_protocol_reconstruction import (
    BlockCompletion,
    MalformedPacket,
    Recipient,
)


class CoreInputContractTests(unittest.TestCase):
    def test_unknown_packets_and_missing_bootstrap_cannot_converge(self):
        recipient = Recipient("participant", "input-generation")
        result = reconstruct_core([(65000, b"opaque")], recipient=recipient)
        self.assertFalse(
            compare_core_view(result, recipient=recipient, expected={"roster": {}})[
                "matches"
            ]
        )

    def test_completion_input_type_and_duplicate_action_witness_fail_explicitly(self):
        recipient = Recipient("participant", "input-generation")
        for completions in ((object(),), (BlockCompletion(0, (7, 7), "a" * 64),)):
            with self.subTest(completions=completions), self.assertRaises(ValueError):
                reconstruct_core([], recipient=recipient, completions=completions)

    def test_malformed_is_distinct_from_unmodeled_native_layout(self):
        with self.assertRaises(MalformedPacket):
            decode_core_packet(12053, b"short")
        with self.assertRaises(UnknownCoreLayout):
            decode_core_packet(12053, struct.pack(">ihBBiB", 99, 7, 2, 0, 6, 0))

    def test_decoder_sources_do_not_import_serializers_or_game_authority(self):
        from wakfu_server import combat_core_reconstruction as module

        tree = ast.parse(Path(module.__file__).read_text())
        imported = {
            node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
        }
        self.assertEqual(
            imported - {"copy", "dataclasses"}, {"combat_protocol_reconstruction"}
        )


class NativeCoreReconstructionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configured = os.environ.get("WAKFU_NATIVE_CORE_FIXTURES")
        if not configured:
            raise unittest.SkipTest(
                "Independent original core native receipt not configured"
            )
        cls.root = Path(configured)
        raw = (cls.root / "native-proof.json").read_bytes()
        cls.receipt = json.loads(raw)
        if not (
            cls.receipt.get("complete") is True
            and cls.receipt.get("returncode") == 0
            and cls.receipt.get("source_stable") is True
            and cls.receipt.get("instrumentation") == "none"
        ):
            raise AssertionError("Original native core proof incomplete")
        cls.proof = hashlib.sha256(raw).hexdigest()
        for name, expected in cls.receipt["fixtures"].items():
            if hashlib.sha256((cls.root / name).read_bytes()).hexdigest() != expected:
                raise AssertionError("Native core fixture hash mismatch: " + name)
        observed = (cls.root / "observations.json").read_bytes()
        if hashlib.sha256(observed).hexdigest() != cls.receipt["observations_sha256"]:
            raise AssertionError("Native core observations mismatch")
        cls.observed = json.loads(observed)

    def packet(self, name):
        return int(name.split("-", 1)[0]), (self.root / (name + ".bin")).read_bytes()

    def recipient(self, spectator=False, generation="native-core"):
        return Recipient("spectator" if spectator else "participant", generation)

    def completed(self, block=0, actions=(7,)):
        return BlockCompletion(block, actions, self.proof)

    def stream(self, spectator=False, declared=False):
        bootstrap = (
            "12044-roster-summon" if declared else "12044" if spectator else "12847"
        )
        return [
            self.packet(bootstrap),
            self.packet("12613-self0-pb0"),
            self.packet("13420"),
            self.packet("12053"),
            self.packet("12514"),
        ]

    def test_independent_original_decoders_agree_on_recovery_and_spectator_bonus(self):
        full = decode_core_packet(*self.packet("12053"))["timeline"]
        self.assertEqual(
            (full["current"], full["progress"][901]),
            (self.observed["current"], self.observed["progress"]),
        )
        spectator = decode_core_packet(*self.packet("12044"))
        self.assertEqual(spectator["bonus_snapshot"]["actors"][22]["counter"], 7)
        self.assertFalse(spectator["bonus_snapshot"]["actors"][-33]["flag"])
        self.assertEqual(spectator["timeline"]["current"], None)

    def test_original_summon_descriptors_keep_controller_property_and_running_identity(
        self,
    ):
        for controlled in (0, 1):
            for excluded in (0, 1):
                with self.subTest(controlled=controlled, excluded=excluded):
                    decoded = decode_core_packet(
                        *self.packet(f"12613-self{controlled}-pb{excluded}")
                    )["summon"]
                    self.assertEqual(
                        (decoded["actor"], decoded["effect_uid"]), (901, 902)
                    )
                    self.assertEqual(decoded["controller"], 901 if controlled else 22)
                    self.assertEqual(decoded["timeline_member"], not excluded)
                    self.assertEqual(
                        (decoded["reference"], decoded["level"]), (3251, 20)
                    )

    def test_participant_and_spectator_converge_after_observed_birth_before_recovery(
        self,
    ):
        for spectator in (False, True):
            with self.subTest(spectator=spectator):
                recipient = self.recipient(spectator)
                result = reconstruct_core(
                    self.stream(spectator),
                    recipient=recipient,
                    completions=(self.completed(),),
                )
                self.assertFalse(result.findings)
                self.assertEqual(result.executed.summons[901]["controller"], 22)
                self.assertTrue(
                    compare_core_view(
                        result,
                        recipient=recipient,
                        expected={
                            "timeline": decode_core_packet(*self.packet("12053"))[
                                "timeline"
                            ],
                            "phase": 2,
                        },
                    )["matches"]
                )

    def test_roster_reference_does_not_construct_summon_or_duplicate_its_later_birth(
        self,
    ):
        recipient = self.recipient(True)
        before = reconstruct_core(
            [self.packet("12044-roster-summon")], recipient=recipient
        )
        self.assertIn(901, before.executed.roster)
        self.assertNotIn(901, before.executed.summons)
        result = reconstruct_core(
            self.stream(True, declared=True),
            recipient=recipient,
            completions=(self.completed(),),
        )
        self.assertFalse(result.findings)
        self.assertEqual(set(result.executed.summons), {901})

    def test_fence_is_not_completion_and_wrong_or_missing_completion_prevents_convergence(
        self,
    ):
        recipient = self.recipient()
        for completions in ((), (self.completed(actions=(8,)),)):
            with self.subTest(completions=completions):
                result = reconstruct_core(
                    self.stream(), recipient=recipient, completions=completions
                )
                self.assertNotIn(901, result.executed.summons)
                self.assertIn(
                    "recovery_before_birth_completion",
                    {x["code"] for x in result.findings},
                )
                self.assertFalse(
                    compare_core_view(
                        result, recipient=recipient, expected={"phase": 2}
                    )["matches"]
                )

    def test_full_timeline_before_birth_exposes_original_duplicate_enrollment(self):
        recipient = self.recipient()
        packets = self.stream()
        packets.insert(1, self.packet("12053"))
        result = reconstruct_core(
            packets, recipient=recipient, completions=(self.completed(),)
        )
        self.assertIn(
            "timeline_enrolled_before_birth", {x["code"] for x in result.findings}
        )
        self.assertEqual(self.observed["old_duplicate_count"], 2)
        self.assertEqual(self.observed["recovered_count"], 1)

    def test_duplicate_native_action_for_distinct_actors_is_rejected_inside_one_block(
        self,
    ):
        packets = [
            self.packet("12847"),
            self.packet("12613-self0-pb0"),
            self.packet("12613-second-actor"),
            self.packet("13420"),
        ]
        self.assertNotEqual(
            decode_core_packet(*packets[1])["summon"]["actor"],
            decode_core_packet(*packets[2])["summon"]["actor"],
        )
        result = reconstruct_core(
            packets, recipient=self.recipient(), completions=(self.completed(),)
        )
        self.assertIn(
            "duplicate_native_action_in_block", {x["code"] for x in result.findings}
        )
        self.assertEqual(set(result.executed.summons), {901})

    def test_native_action_reuse_in_distinct_generations_is_not_global_collision(self):
        for generation in ("connection-one", "connection-two"):
            recipient = self.recipient(generation=generation)
            result = reconstruct_core(
                self.stream(), recipient=recipient, completions=(self.completed(),)
            )
            self.assertFalse(result.findings)
        with self.assertRaises(ValueError):
            compare_core_view(
                result,
                recipient=self.recipient(generation="stale"),
                expected={"phase": 2},
            )

    def test_native_repeated_available_members_are_preserved_with_unique_progress(self):
        value = decode_timeline((self.root / "timeline-repeated.bin").read_bytes())
        self.assertEqual(
            value["available"].count(901), self.observed["repeated_available_count"]
        )
        self.assertEqual(value["next_order"].count(901), 1)
        self.assertEqual(value["progress"][901], 3)
        self.assertEqual(value["current"], 901)

    def test_property114_membership_mismatch_and_wrong_role_are_not_accepted(self):
        packets = self.stream()
        packets[1] = self.packet("12613-self0-pb1")
        result = reconstruct_core(
            packets, recipient=self.recipient(), completions=(self.completed(),)
        )
        self.assertIn(
            "property114_actor_enrolled_in_timeline",
            {x["code"] for x in result.findings},
        )
        result = reconstruct_core(
            self.stream(True),
            recipient=self.recipient(),
            completions=(self.completed(),),
        )
        self.assertIn("recipient_role_mismatch", {x["code"] for x in result.findings})

    def test_unmodeled_private_stats_and_books_cannot_be_requested_as_verified_projection(
        self,
    ):
        recipient = self.recipient()
        result = reconstruct_core(
            self.stream(), recipient=recipient, completions=(self.completed(),)
        )
        for expected in ({"private_stats": {}}, {"spellbooks": {}}):
            with self.subTest(expected=expected), self.assertRaises(ValueError):
                compare_core_view(result, recipient=recipient, expected=expected)

    def test_actual_owned_and_spectator_snapshot_producers_preserve_roster_and_closed_birth_order(
        self,
    ):
        from types import SimpleNamespace
        from test_combat_reconnect_summon_timeline import fixture
        from wakfu_server.combat_reconnect_snapshot import owned_snapshot
        from wakfu_server.combat_spectator_snapshot import current_snapshot

        for spectator in (False, True):
            for current_summon in (False, True):
                with self.subTest(spectator=spectator, current_summon=current_summon):
                    fight, summon, shared = fixture(current_summon)
                    shared.instance_id = 0
                    packets = (
                        current_snapshot(
                            fight,
                            shared,
                            actor_payload=lambda *args: (b"opaque-stats", b"\x00\x00"),
                            deadline_ms=31000,
                        )
                        if spectator
                        else owned_snapshot(
                            fight,
                            shared,
                            SimpleNamespace(account_id=1),
                            actor_payload=lambda *args: (b"opaque-stats", b"\x00\x00"),
                        )
                    )
                    core_packets = list(packets)
                    birth = next(
                        decode_core_packet(*packet)
                        for packet in core_packets
                        if packet[0] == 12613
                    )
                    recipient = self.recipient(spectator)
                    result = reconstruct_core(
                        core_packets,
                        recipient=recipient,
                        completions=(self.completed(actions=(birth["action"],)),),
                    )
                    self.assertFalse(result.findings)
                    self.assertIn(summon.id, result.executed.summons)
                    self.assertEqual(
                        result.executed.timeline["current"], fight.current.id
                    )
                    self.assertEqual(result.executed.timeline["progress"][summon.id], 3)
                    self.assertEqual(
                        result.executed.timeline["available"].count(summon.id),
                        fight.order.count(summon.id),
                    )
                    if spectator:
                        declared = decode_core_packet(*core_packets[0])["entities"]
                        self.assertIn(summon.id, declared)
                        self.assertIn(summon.id, result.executed.roster)

    def test_actual_spectator_recovery_moved_before_birth_is_rejected(self):
        from test_combat_reconnect_summon_timeline import fixture
        from wakfu_server.combat_spectator_snapshot import current_snapshot

        fight, summon, shared = fixture(True)
        shared.instance_id = 0
        packets = current_snapshot(
            fight,
            shared,
            actor_payload=lambda *args: (b"opaque-stats", b"\x00\x00"),
            deadline_ms=31000,
        )
        core_packets = list(packets)
        birth_index = next(
            index for index, packet in enumerate(core_packets) if packet[0] == 12613
        )
        recovery_index = next(
            index for index, packet in enumerate(core_packets) if packet[0] == 12053
        )
        birth = decode_core_packet(*core_packets[birth_index])
        completions = (self.completed(actions=(birth["action"],)),)
        recipient = self.recipient(True)
        valid = reconstruct_core(
            core_packets, recipient=recipient, completions=completions
        )
        self.assertFalse(valid.findings)
        self.assertIn(summon.id, valid.executed.summons)
        self.assertLess(birth_index, recovery_index)
        # Inject the previously observed wrong ordering without a live old backend.
        # Every producer packet stays byte-identical; only recovery placement changes.
        recovery = core_packets.pop(recovery_index)
        core_packets.insert(birth_index, recovery)
        self.assertCountEqual(core_packets, list(packets))
        result = reconstruct_core(
            core_packets, recipient=recipient, completions=completions
        )
        self.assertIn(
            "timeline_enrolled_before_birth", {x["code"] for x in result.findings}
        )

    def test_birth_cannot_reuse_an_independently_declared_existing_leader_identity(
        self,
    ):
        from wakfu_server.combat_protocol_reconstruction import _Reader

        raw = bytearray(self.packet("12044-roster-summon")[1])
        reader = _Reader(bytes(raw))
        reader.read("ibqqq")
        reader.blob("i")
        reader.blob("h")
        struct.pack_into(">q", raw, reader.offset + 8, 901)
        packets = [
            (12044, bytes(raw)),
            self.packet("12613-self0-pb0"),
            self.packet("13420"),
        ]
        result = reconstruct_core(
            packets, recipient=self.recipient(True), completions=(self.completed(),)
        )
        self.assertIn(
            "summon_reuses_known_world_identity", {x["code"] for x in result.findings}
        )
        self.assertNotIn(901, result.executed.summons)

    def retirement_fixture(self):
        configured = os.environ.get("WAKFU_NATIVE_RETIREMENT_FIXTURES")
        if not configured:
            self.skipTest("Independent attached retirement proof not configured")
        root = Path(configured)
        raw = (root / "native-proof.json").read_bytes()
        receipt = json.loads(raw)
        self.assertTrue(receipt.get("complete"))
        self.assertEqual(receipt.get("returncode"), 0)
        self.assertEqual(receipt.get("instrumentation"), "none")
        for name, digest in receipt["fixtures"].items():
            self.assertEqual(
                hashlib.sha256((root / name).read_bytes()).hexdigest(), digest
            )
        observed = (root / "observations.json").read_bytes()
        self.assertEqual(
            hashlib.sha256(observed).hexdigest(), receipt["observations_sha256"]
        )
        facts = json.loads(observed)
        self.assertTrue(facts["state2_completed"])
        self.assertTrue(facts["after_completion_out_of_play"])
        self.assertTrue(facts["after_completion_roster_retained"])
        self.assertFalse(facts["after_completion_physical_registered"])
        self.assertFalse(facts["before_completion_timeline_registered"])
        self.assertTrue(facts["before_completion_removed_timeline_record"])
        self.assertFalse(facts["after_completion_timeline_registered"])
        self.assertFalse(facts["after_completion_removed_timeline_record"])
        self.assertTrue(facts["completion_callback_successful"])
        return root, hashlib.sha256(raw).hexdigest(), facts

    def test_attested_state2_completion_retires_physical_registration_and_keeps_roster(
        self,
    ):
        from wakfu_server.combat_core_reconstruction import NativeRetirementContext

        root, proof, facts = self.retirement_fixture()
        recipient = self.recipient()
        # This isolated slice supplies the separately verified prior fem.eT
        # boundary. Do not restore a contradictory active901 recovery first.
        packets = self.stream()[:3] + [
            self.packet("12514"),
            (12727, (root / "12727-state2.bin").read_bytes()),
        ]
        context = NativeRetirementContext(
            facts["fight"], facts["actor"], True, True, True, True, proof
        )
        result = reconstruct_core(
            packets,
            recipient=recipient,
            completions=(self.completed(), BlockCompletion(1, (7,), proof)),
            retirement_contexts=(context,),
        )
        self.assertFalse(result.findings)
        self.assertIn(901, result.executed.roster)
        expected = {
            901: dict(
                state="OUT_OF_PLAY",
                physical_registered=False,
                roster_retained=True,
                timeline_member=False,
                saved_removed_record=False,
            )
        }
        self.assertTrue(
            compare_core_view(
                result, recipient=recipient, expected={"retirements": expected}
            )["matches"]
        )
        self.assertFalse(
            compare_core_view(
                result,
                recipient=recipient,
                expected={"timeline": result.executed.timeline},
            )["matches"]
        )

    def test_raw_state2_receipt_does_not_retire_without_observed_completion(self):
        from wakfu_server.combat_core_reconstruction import NativeRetirementContext

        root, proof, facts = self.retirement_fixture()
        context = NativeRetirementContext(
            facts["fight"], facts["actor"], True, True, True, True, proof
        )
        result = reconstruct_core(
            self.stream()[:3]
            + [self.packet("12514"), (12727, (root / "12727-state2.bin").read_bytes())],
            recipient=self.recipient(),
            completions=(self.completed(),),
            retirement_contexts=(context,),
        )
        self.assertEqual(result.received.fighter_status_messages[901], 2)
        self.assertEqual(result.executed.retirements[901]["state"], "OFF_PLAY")
        self.assertTrue(result.executed.retirements[901]["physical_registered"])
        self.assertIn(901, result.executed.roster)
        self.assertTrue(result.pending)
        self.assertTrue(result.executed.retirements[901]["saved_removed_record"])
        with self.assertRaises(ValueError):
            NativeRetirementContext(
                facts["fight"], facts["actor"], True, True, False, True, proof
            )
        with self.assertRaises(ValueError):
            NativeRetirementContext(
                facts["fight"], facts["actor"], True, True, True, False, proof
            )
        contradicted = reconstruct_core(
            self.stream() + [(12727, (root / "12727-state2.bin").read_bytes())],
            recipient=self.recipient(),
            completions=(self.completed(), BlockCompletion(1, (7,), proof)),
            retirement_contexts=(context,),
        )
        self.assertIn(
            "native_retirement_context_contradicts_timeline",
            {x["code"] for x in contradicted.findings},
        )
        self.assertNotIn(901, contradicted.executed.retirements)

    def test_unestablished_statuses_and_missing_offplay_authority_do_not_infer_retirement(
        self,
    ):
        root, proof, facts = self.retirement_fixture()
        for state in (0, 1, 2, 3, 7):
            with self.subTest(state=state):
                result = reconstruct_core(
                    self.stream()
                    + [(12727, (root / f"12727-state{state}.bin").read_bytes())],
                    recipient=self.recipient(),
                    completions=(self.completed(), BlockCompletion(1, (7,), proof)),
                )
                self.assertEqual(result.received.fighter_status_messages[901], state)
                self.assertNotIn(901, result.executed.retirements)
                self.assertIn(
                    "fighter_retirement_semantics_not_proven",
                    {x["code"] for x in result.findings},
                )
                self.assertIn(901, result.executed.roster)

    def test_exploration_despawn_cannot_delete_a_registered_combat_roster(self):
        recipient = self.recipient()
        body = b"\x00\x00\x01" + struct.pack(">bq", 1, 901)
        result = reconstruct_core(
            self.stream() + [(12304, body)],
            recipient=recipient,
            completions=(self.completed(),),
        )
        self.assertIn(901, result.executed.roster)
        self.assertIn(
            "world_despawn_not_combat_retirement", {x["code"] for x in result.findings}
        )
