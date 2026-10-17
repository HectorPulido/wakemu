"""Captured actions replay deterministically through the actual combat engine."""
import copy
import json
import random
import struct
import tempfile
from pathlib import Path
import unittest

from wakfu_server.combat_reproduction import (
    capture_request,
    execute_case,
    record_expectation,
    compare_expectation,
    write_case,
    read_case,
    controlled_environment,
)
from wakfu_server.combat_reproduction_state import decode_state


class CombatReproductionTests(unittest.TestCase):
    def test_observed_real_action_inputs_replay_and_mismatch_is_infrastructure(self):
        from wakfu_server.combat_input_observation import (
            observe_combat_inputs,
            InputReplayMismatch,
        )
        from wakfu_server.combat_reproduction import ReproductionClock
        from wakfu_server.combat_reproduction_actions import prepare_context, execute

        case, _ = self.capture()
        state = decode_state(case["before"])
        runtime, action, inputs = state["runtime"], state["action"], state["inputs"]
        rng = random.Random()
        rng.setstate(state["rng_state"])
        clock = ReproductionClock(case["clocks"])
        with controlled_environment(case["clocks"], case["policies"]):
            context = prepare_context(runtime, action, inputs, rng, clock)
            with observe_combat_inputs() as observation:
                original = execute(
                    runtime, action, inputs, rng, clock, prepared_context=context
                )
        snapshot = observation.snapshot()
        replayed = decode_state(execute_case(case, observations=snapshot)["result"])
        self.assertEqual(replayed["packets"], original["packets"])
        self.assertEqual(replayed["plan"], original["plan"])
        self.assertEqual(
            replayed["runtime"].fight.actors[-7].hp, runtime.fight.actors[-7].hp
        )
        self.assertTrue(replayed["input_replay"]["ownership_known"])
        self.assertEqual(
            replayed["observed_rng_streams"][0]["final_state"], rng.getstate()
        )
        self.assertIsNone(replayed["rng_state"])
        bad = copy.deepcopy(snapshot)
        bad["events"][0]["label"] = "unobserved-binding"
        with self.assertRaises(InputReplayMismatch):
            execute_case(case, observations=bad)

    def test_capture_rejects_unknown_policy_fields_without_serializing_them(self):
        from unittest.mock import patch

        with patch("wakfu_server.combat_reproduction.encode_state") as encode:
            with self.assertRaisesRegex(ValueError, "policy manifest"):
                capture_request(
                    None,
                    {},
                    {},
                    random.Random(42),
                    policies={"unrecognized_private_setting": "private"},
                )
            encode.assert_not_called()

    def test_capture_does_not_override_process_clocks_or_environment(self):
        import os
        import time
        from unittest.mock import patch

        wall, monotonic = time.time, time.monotonic
        environment = dict(os.environ)

        def observe(value):
            self.assertIs(time.time, wall)
            self.assertIs(time.monotonic, monotonic)
            self.assertEqual(dict(os.environ), environment)
            return {"captured": True}

        with patch(
            "wakfu_server.combat_reproduction.encode_state", side_effect=observe
        ), patch(
            "wakfu_server.combat_reproduction.source_identity", return_value={}
        ), patch(
            "wakfu_server.combat_reproduction.catalog_identity", return_value={}
        ):
            case = capture_request(
                None,
                {},
                {},
                random.Random(42),
                clocks={"wall_time_ns": 1, "monotonic_ns": 2},
                policies={
                    "WAKFU_NATIVE_AREA_CALLBACKS": "0",
                    "WAKFU_NATIVE_GRANTED_CAST": "1",
                },
            )
        self.assertEqual(case["before"], {"captured": True})

    def capture(self, kind="player_spell", *, body=None):
        import test_combat_reproduction_actions as fixtures

        runtime, inputs = fixtures.ReproductionActionTests().fixture()
        target = runtime.fight.actors[-7].position
        action = {
            "type": kind,
            "body": body
            if body is not None
            else struct.pack(">qqiih", 7, (7 << 32) | 6266, *target),
            "owner_id": 3,
            "critical": None,
        }
        return (
            capture_request(
                runtime,
                action,
                inputs,
                random.Random(42),
                clocks={
                    "wall_time_ns": 1700000000000000000,
                    "monotonic_ns": 123000000000,
                },
                recipients=(3,),
            ),
            runtime,
        )

    def test_exact_native_cast_replay_and_input_isolation(self):
        case, runtime = self.capture()
        before = copy.deepcopy(case)
        first = execute_case(case)
        record_expectation(case, first)
        second = execute_case(json.loads(json.dumps(case)))
        self.assertEqual(
            first["status"], "accepted", decode_state(first["result"])["error"]
        )
        self.assertEqual(first["sha256"], second["sha256"])
        self.assertTrue(compare_expectation(case, second)["matches"])
        self.assertEqual(case["before"], before["before"])
        self.assertEqual(runtime.action_id, 1)
        state = decode_state(second["result"])
        self.assertTrue(state["packets"])
        self.assertLess(
            state["runtime"].fight.actors[-7].hp, runtime.fight.actors[-7].hp
        )

    def test_rejection_reproduces_decoder_error_and_rollback(self):
        case, _ = self.capture(body=b"malformed")
        result = execute_case(case)
        self.assertEqual(result["status"], "rejected")
        observed = decode_state(result["result"])
        self.assertEqual(observed["packets"], ())
        self.assertTrue(observed["rollback"]["runtime_unchanged"])
        self.assertTrue(observed["rollback"]["rng_unchanged"])
        self.assertEqual(result["sha256"], execute_case(case)["sha256"])

    def test_pending_ack_and_session_generation_are_captured(self):
        from wakfu_server.combat_ack_barrier import AckBarrier
        from wakfu_server.combat_shared import Session

        case, runtime = self.capture()
        runtime.pending = [(12613, b"exact pending")]
        runtime.awaiting_ack = 7
        session = Session(3, 7, "fixture-generation", 1134, 0)
        barrier = AckBarrier()
        barrier.arm(7, [session])
        captured = decode_state(case["before"])
        case = capture_request(
            runtime,
            captured["action"],
            captured["inputs"],
            random.Random(42),
            clocks=case["clocks"],
            session={"participants": {3: session}, "ack": barrier},
        )
        saved = decode_state(case["before"])
        self.assertEqual(saved["runtime"].pending, [(12613, b"exact pending")])
        self.assertEqual(saved["session"]["ack"].expected, {3: "fixture-generation"})
        self.assertEqual(execute_case(case)["status"], "rejected")

    def test_clock_and_policies_restore_after_context(self):
        import os
        import time

        original = time.time
        old = os.environ.get("WAKFU_NATIVE_GRANTED_CAST")
        with controlled_environment(
            {"wall_time_ns": 123000000000, "monotonic_ns": 45000000000},
            {"WAKFU_NATIVE_AREA_CALLBACKS": "0", "WAKFU_NATIVE_GRANTED_CAST": "1"},
        ) as clock:
            self.assertEqual(time.time(), 123)
            self.assertEqual(time.time_ns(), 123000000000)
            self.assertEqual(clock(), 45)
            self.assertEqual(time.monotonic_ns(), 45000000000)
        self.assertIs(time.time, original)
        self.assertEqual(os.environ.get("WAKFU_NATIVE_GRANTED_CAST"), old)

    def test_modified_expectation_reports_difference_without_raw_values(self):
        case, _ = self.capture(body=b"bad")
        result = execute_case(case)
        record_expectation(case, result)
        different = copy.deepcopy(result)
        different["result"]["schema"] = "changed"
        from wakfu_server.combat_reproduction import digest

        different["sha256"] = digest(different["result"])
        comparison = compare_expectation(case, different)
        self.assertFalse(comparison["matches"])
        self.assertEqual(comparison["differences"], ["result.schema: value differs"])

    def test_file_roundtrip_private_permissions_and_schema_guard(self):
        case, _ = self.capture(body=b"bad")
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "case.json"
            write_case(path, case)
            self.assertEqual(read_case(path), case)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)
            case["schema"] = "future-version"
            with self.assertRaises(ValueError):
                write_case(path, case)

    def test_bad_authority_is_an_infrastructure_error_not_a_game_rejection(self):
        from wakfu_server.combat_reproduction_state import encode_state
        from wakfu_server.combat_reproduction_actions import ReproductionContextError

        case, _ = self.capture(body=b"bad")
        state = decode_state(case["before"])
        state["inputs"]["authority_recipe"] = "unknown-recipe"
        case["before"] = encode_state(state)
        with self.assertRaises(ReproductionContextError):
            execute_case(case)

    def test_catalog_revision_mismatch_rejects_before_engine_execution(self):
        case, _ = self.capture(body=b"bad")
        case["catalog"]["revision"] = "different-release"
        with self.assertRaisesRegex(ValueError, "catalog differs"):
            execute_case(case)

    def test_bundle_binding_detects_replaced_manifest_even_for_rejected_action(self):
        from wakfu_server.combat_reproduction import (
            bind_catalog_bundle,
            verify_catalog_bundle,
            digest,
        )

        inventory = {"fixture.json": "a" * 64}
        case = {
            "catalog": {
                "revision": "fixture",
                "inventory_sha256": digest(inventory),
                "bundle_sha256": None,
            }
        }
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "catalog.json"
            manifest = {"revision": "fixture", "published_hashes": inventory}
            path.write_text(json.dumps(manifest))
            bind_catalog_bundle(case, root)
            verify_catalog_bundle(case, root)
            path.write_text(json.dumps(dict(manifest, another="manifest")))
            with self.assertRaisesRegex(ValueError, "replaced or modified"):
                verify_catalog_bundle(case, root)


if __name__ == "__main__":
    unittest.main()
