"""Chosen NPC commits replay native authority without requesting a decision."""
import os
import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import test_native_oracle as fixture_module
from wakfu_ai.native.native_stats import NativeStats
from wakfu_ai.native.native_deadline import bounded
from wakfu_ai.native import native_deadline
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_input_observation import (
    observe_combat_inputs,
    InputReplayMismatch,
)
from wakfu_server.combat_npc_reproduction import (
    NPCCommitCapture,
    publication_correlations,
    replay_npc_receipt,
    UnsupportedNPCReproduction,
    _sdk_modules,
)
from wakfu_server.combat_reproduction_state import decode_state, encode_state
from wakfu_server.spells import default_deck


class NativeNPCReproductionTests(unittest.TestCase):
    def test_restored_provider_descriptors_aliases_keep_deadline_check_trace(self):
        from wakfu_server.combat_npc_reproduction import _routine, _provider
        from wakfu_ai.context.native_fingerprint import fingerprint

        def serializer(*args):
            return b""

        restored = _routine(serializer, _provider(serializer))
        original = dict(
            stats_serializer=serializer,
            runtime_stats_serializer=serializer,
            clock=time.monotonic,
        )
        private = dict(
            stats_serializer=restored,
            runtime_stats_serializer=restored,
            clock=_routine(lambda: 12.0, _provider(time.monotonic)),
        )
        hashes, tapes = [], []
        token = native_deadline._ACTIVE.set((20.0, lambda: 12.0))
        try:
            for graph in (original, private):
                with observe_combat_inputs() as observation:
                    hashes.append(fingerprint(graph))
                tapes.append(observation.snapshot())
        finally:
            native_deadline._ACTIVE.reset(token)
        self.assertEqual(hashes[0], hashes[1])
        self.assertEqual(tapes[0], tapes[1])

    def test_standalone_planner_import_needs_no_world_server(self):
        directory = str(Path(__file__).resolve().parents[1])
        script = (
            "import sys; sys.path.insert(0, " + repr(directory) + "); "
            "import wakfu_ai.planning.query_search; "
            "from wakfu_ai.native.native_deadline import bounded, remaining; "
            "assert 'wakfu_server' not in sys.modules; "
            "scope = bounded(20.0, clock=lambda: 12.0); scope.__enter__(); "
            "assert remaining() == 8.0; scope.__exit__(None, None, None)"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, "-I", "-c", script],
                cwd=directory,
                capture_output=True,
                text=True,
                timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_trusted_sdk_loader_keeps_wakfu_ai_namespace(self):
        from wakfu_server.combat_npc_reproduction import _sdk_modules

        oracle, stats, _ = _sdk_modules()
        self.assertTrue(oracle.__name__.endswith(".wakfu_ai.native.native_oracle"))
        self.assertTrue(stats.__name__.endswith(".wakfu_ai.native.native_stats"))

    def test_deadline_observation_keeps_exactly_one_original_clock_read(self):
        clock = unittest.mock.Mock(return_value=12.0)
        token = native_deadline._ACTIVE.set((20.0, clock))
        try:
            with observe_combat_inputs() as observation:
                self.assertEqual(native_deadline.remaining(), 8.0)
        finally:
            native_deadline._ACTIVE.reset(token)
        clock.assert_called_once_with()
        self.assertEqual(
            observation.snapshot()["events"],
            [
                dict(
                    sequence=1,
                    kind="clock",
                    label="native_deadline.monotonic",
                    value=12.0,
                )
            ],
        )

    def setup_native(self):
        fixture = fixture_module.NativeOracleTests.wonejo_fixture()
        runtime = RuntimeMessages(fixture.fight)
        oracle_module, stats_module, _ = _sdk_modules()
        oracle = oracle_module.NativeOracle(
            runtime,
            characters={fixture.pc.id: fixture.character},
            monsters={fixture.npc.id: fixture.monster},
            decks={fixture.pc.id: default_deck(fixture.character)},
            excluded_decks={fixture.pc.id: frozenset()},
            viewer_id=fixture.pc.id,
            flags={},
        )
        serializer = stats_module.NativeStats(
            characters=oracle.characters,
            monsters=oracle.monsters,
            fight_id=runtime.fight.id,
            map_id=fixture.character["map_id"],
        )
        action = dict(
            type="cast",
            spellId=7962,
            level=1,
            targetId=fixture.pc.id,
            target=list(fixture.pc.position),
        )
        return fixture, runtime, oracle, serializer, action

    def deadline_for(self, oracle):
        return importlib.import_module(
            type(oracle).__module__.rsplit(".", 1)[0] + ".native_deadline"
        )

    def record(self, oracle, serializer, action):
        capture = NPCCommitCapture(oracle, action, serializer)
        error = None
        with observe_combat_inputs(limit=8192) as observation:
            try:
                packets = oracle.commit(action, stats_serializer=serializer)
                capture.packets(packets)
            except Exception as failure:
                error = failure
        return capture.receipt(observation, error)

    def test_native_npc_cast_and_injured_target_death_replay_exactly(self):
        from wakfu_server.combat_hp_raw import set_hp_raw_current

        for lethal in (False, True):
            with self.subTest(lethal=lethal):
                fixture, runtime, oracle, serializer, action = self.setup_native()
                if lethal:
                    set_hp_raw_current(fixture.pc, 1)
                receipt = self.record(oracle, serializer, action)
                self.assertEqual(receipt["status"], "accepted", receipt["error"])
                self.assertEqual(receipt["incomplete"], [])
                # No Store/HTTP/planner entry is part of the trusted recipe.
                with patch(
                    "wakfu_ai.bridge.world_entry.run_npc_turn",
                    side_effect=AssertionError("search"),
                ):
                    result = replay_npc_receipt(receipt)
                self.assertTrue(result["matches"], result["comparison"])
                self.assertEqual(
                    publication_correlations(runtime), (receipt["incident_id"],)
                )
                if lethal:
                    self.assertEqual(runtime.fight.actors[fixture.pc.id].hp, 0)
                    self.assertTrue(
                        any(opcode == 12727 for opcode, _ in result["packets"])
                    )

    def test_native_end_turn_retains_ack_barrier(self):
        fixture, runtime, oracle, serializer, _ = self.setup_native()
        receipt = self.record(oracle, serializer, {"type": "end_turn"})
        self.assertEqual(receipt["status"], "accepted")
        self.assertIsNotNone(runtime.awaiting_ack)
        result = replay_npc_receipt(receipt)
        self.assertTrue(result["matches"], result["comparison"])

    def test_owned_npc_route_replays_and_spends_actual_mp(self):
        fixture, runtime, oracle, serializer, _ = self.setup_native()
        origin = fixture.npc.position
        routes = [
            target
            for source, target in fixture.fight.edges
            if source == origin and target != fixture.pc.position
        ]
        self.assertTrue(routes)
        before = fixture.npc.mp
        receipt = self.record(
            oracle, serializer, dict(type="move", path=[list(routes[0])])
        )
        self.assertEqual(receipt["status"], "accepted")
        self.assertLess(runtime.fight.current.mp, before)
        result = replay_npc_receipt(receipt)
        self.assertTrue(result["matches"], result["comparison"])

    def test_rejected_illegal_action_replays_without_resources_or_packets(self):
        _, runtime, oracle, serializer, action = self.setup_native()
        action["level"] = 32767
        before = encode_state(runtime)
        receipt = self.record(oracle, serializer, action)
        self.assertEqual(receipt["status"], "raised")
        self.assertEqual(encode_state(runtime), before)
        result = replay_npc_receipt(receipt)
        self.assertTrue(result["matches"])
        self.assertEqual(result["packets"], ())

    def test_custom_serializer_is_explicitly_unqualified(self):
        _, _, oracle, serializer, action = self.setup_native()
        capture = NPCCommitCapture(oracle, action, lambda *_: b"")
        self.assertIn("unqualified_commit_serializer", capture.incomplete)

    def bind_actual_ready_providers(self, fixture, initial):
        from wakfu_server.combat_session_adapter import CombatSessionAdapter
        from wakfu_server.combat_server_spell import prepare_server_initialization

        # wonejo_fixture establishes placement/readiness and snapshots only.
        # Run the actual initialization/start transaction before turn events;
        # setting its completion flag directly would bypass the lifecycle.
        deck = default_deck(fixture.character)
        next_action = initial.action_id + 1
        initialized, _ = prepare_server_initialization(
            fixture.character,
            {fixture.npc.id: fixture.monster},
            initial.fight,
            fixture.character["account_id"],
            deck,
            action_id=next_action,
            player_characters={fixture.pc.id: fixture.character},
            deck_blobs={fixture.pc.id: deck},
            fight_start=True,
        )
        initial.fight = initialized
        initial.action_id = next_action
        fixture.fight = initialized
        fixture.pc = initialized.actors[fixture.character["id"]]
        fixture.npc = initialized.actors[fixture.monster["id"]]

        class Store:
            def character(self, owner, identity):
                if (
                    owner != fixture.character["account_id"]
                    or identity != fixture.character["id"]
                ):
                    raise AssertionError("foreign fixture source")
                return fixture.character

        def already_initialized(fight, owner, ready, **providers):
            # Obtain actual ready closures without initializing this existing
            # native fixture twice. No callback or action is replaced.
            fields = (
                "stats_serializer",
                "runtime_stats_serializer",
                "turn_end_provider",
                "turn_start_provider",
                "expiration_runtime_factory",
            )
            runtime = RuntimeMessages(
                fight, **{field: providers[field] for field in fields}
            )
            runtime.action_id = initial.action_id
            return fight, runtime, ()

        with patch(
            "wakfu_server.combat_ready.prepare_ready", side_effect=already_initialized
        ):
            return (
                CombatSessionAdapter(Store())
                .ready_transition(
                    SimpleNamespace(
                        account_id=fixture.character["account_id"],
                        character_id=fixture.pc.id,
                    ),
                    initial.fight,
                    initial,
                    True,
                    {fixture.npc.id: fixture.monster},
                    fight_start=True,
                    area_callbacks=False,
                )
                .runtime
            )

    def test_actual_ready_providers_and_active_deadline_replay_chosen_action(self):
        for kind in ("cast", "end_turn"):
            with self.subTest(kind=kind):
                fixture, initial, prototype, serializer, action = self.setup_native()
                runtime = self.bind_actual_ready_providers(fixture, initial)
                oracle = type(prototype)(
                    runtime,
                    characters=prototype.characters,
                    monsters=prototype.monsters,
                    decks=prototype.decks,
                    excluded_decks=prototype.excluded_decks,
                    viewer_id=prototype.viewer_id,
                    flags=prototype.flags,
                )
                if kind == "end_turn":
                    action = {"type": "end_turn"}
                else:
                    action["target"] = list(fixture.pc.position)
                with self.deadline_for(oracle).bounded(time.monotonic() + 600):
                    receipt = self.record(oracle, serializer, action)
                self.assertEqual(receipt["incomplete"], [])
                self.assertTrue(receipt["deadline_active"])
                self.assertEqual(receipt["status"], "accepted", receipt["error"])
                tape = decode_state(receipt["observations"])
                self.assertTrue(
                    any(
                        row["label"] == "native_deadline.monotonic"
                        for row in tape["events"]
                    )
                )
                transported = json.loads(json.dumps(receipt))
                result = replay_npc_receipt(transported)
                self.assertTrue(result["matches"], result["comparison"])

    def test_partial_initialization_turn_boundary_rejection_replays_atomically(self):
        _, runtime, oracle, serializer, _ = self.setup_native()
        runtime.turn_end_provider = oracle.live_end_boundary
        before = encode_state(runtime)
        receipt = self.record(oracle, serializer, {"type": "end_turn"})
        self.assertEqual(receipt["status"], "raised")
        self.assertEqual(
            receipt["error"],
            dict(
                type="builtins.ValueError",
                message="Native participant initialization/start is incomplete",
            ),
        )
        self.assertEqual(encode_state(runtime), before)
        self.assertTrue(replay_npc_receipt(receipt)["matches"])

    def test_expired_active_deadline_replays_exact_timeout_without_mutation(self):
        _, runtime, oracle, serializer, action = self.setup_native()
        before = encode_state(runtime)
        deadline = self.deadline_for(oracle)
        token = deadline._ACTIVE.set((time.monotonic() - 1, time.monotonic))
        try:
            receipt = self.record(oracle, serializer, action)
        finally:
            deadline._ACTIVE.reset(token)
        self.assertEqual(receipt["incomplete"], [])
        self.assertEqual(receipt["status"], "raised")
        self.assertEqual(receipt["error"]["type"], "builtins.TimeoutError")
        self.assertEqual(encode_state(runtime), before)
        result = replay_npc_receipt(receipt)
        self.assertTrue(result["matches"])
        self.assertEqual(result["packets"], ())

    def test_unknown_native_environment_values_never_enter_receipt(self):
        _, _, oracle, serializer, action = self.setup_native()
        oracle.flags["native_environment"] = {
            "WAKFU_NATIVE_PASSWORD": "PRIVATE-SECRET",
            "WAKFU_NATIVE_GRANTED_CAST": "PRIVATE-SECRET",
        }
        capture = NPCCommitCapture(oracle, action, serializer)
        self.assertNotIn("PRIVATE-SECRET", repr(capture.before))
        self.assertIn("unknown_native_environment_entries", capture.incomplete)

    def test_rng_input_mismatch_remains_infrastructure_failure(self):
        _, _, oracle, serializer, action = self.setup_native()
        receipt = self.record(oracle, serializer, action)
        tape = decode_state(receipt["observations"])
        next(row for row in tape["events"] if row["kind"] == "rng")[
            "label"
        ] = "foreign-stream"
        receipt["observations"] = encode_state(tape)
        with self.assertRaises(InputReplayMismatch):
            replay_npc_receipt(receipt)

    def test_automatic_scope_is_passive_and_keeps_failure_atomic(self):
        _, runtime, oracle, _, action = self.setup_native()
        before = encode_state(runtime)
        receipts = []

        def failed_serializer(*_):
            raise ValueError("actual serializer rejection")

        with patch.dict(
            os.environ, {"WAKFU_COMBAT_INCIDENT_DIR": "/unused-private-writer"}
        ), patch(
            "wakfu_server.combat_incident_capture._enqueue",
            side_effect=lambda root, row: receipts.append(row),
        ):
            with self.assertRaisesRegex(ValueError, "actual serializer rejection"):
                oracle.commit(action, stats_serializer=failed_serializer)
        self.assertEqual(encode_state(runtime), before)
        self.assertEqual(len(receipts), 1)
        self.assertEqual(receipts[0]["status"], "raised")
        self.assertFalse(receipts[0]["replay_qualified"])
        with self.assertRaises(UnsupportedNPCReproduction):
            replay_npc_receipt(receipts[0])
