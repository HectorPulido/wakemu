"""Small guard parity and non-throwing diagnostic checks; no catalog/DB fixtures."""
import importlib.util
from contextvars import ContextVar
from types import ModuleType
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path(__file__).with_name("combat_retained_gc_boundary.py")
sys.path.insert(0, str(ROOT / "server"))
NAME = "wakfu_server.combat.combat_retained_gc_boundary"
spec = importlib.util.spec_from_file_location(NAME, SOURCE)
module = importlib.util.module_from_spec(spec)
sys.modules[NAME] = module
spec.loader.exec_module(module)
runtime_module = ModuleType("wakfu_server.combat.combat_runtime_messages")
runtime_module.RuntimeMessages = type("RuntimeMessages", (), {})
sys.modules[runtime_module.__name__] = runtime_module


class ThrowingDiagnosticInput:
    accesses = 0

    @property
    def __dict__(self):
        type(self).accesses += 1
        raise RuntimeError("diagnostic must not propagate")


class DiagnosticIsolationTests(unittest.TestCase):
    def test_opt_in_preserves_guard_result_and_logger_failure_is_swallowed(self):
        module._GC_DIAGNOSTIC_SEEN.clear()
        module._GC_DIAGNOSTICS = False
        with patch.object(module._GC_DIAGNOSTIC_LOG, "warning") as log:
            disabled_result = module.prepare_retired_gc(None, None, None, None)
        log.assert_not_called()

        module._GC_DIAGNOSTIC_SEEN.clear()
        module._GC_DIAGNOSTICS = True
        with patch.object(module._GC_DIAGNOSTIC_LOG, "warning") as log:
            enabled_result = module.prepare_retired_gc(None, None, None, None)
        self.assertEqual(enabled_result, disabled_result)
        self.assertIsNone(enabled_result)
        log.assert_called_once()
        self.assertIn("reason=exact_type", log.call_args.args[-1])

        with patch.object(
            module._GC_DIAGNOSTIC_LOG,
            "warning",
            side_effect=RuntimeError("sink unavailable"),
        ):
            module._gc_diagnostic(
                ThrowingDiagnosticInput(), "probe", reason="logger_failure"
            )
            self.assertEqual(ThrowingDiagnosticInput.accesses, 0)
            module._GC_DIAGNOSTIC_SEEN.clear()
            self.assertIsNone(module.prepare_retired_gc(None, None, None, None))

    def test_quiescence_reports_first_scalar_boundary_reason(self):
        pending = ContextVar("test_pending", default=frozenset())
        read_pass = ContextVar("test_read_pass", default=())
        frames = ContextVar("test_frames", default=())
        pending_module = ModuleType("wakfu_server.combat.combat_pending_state")
        pending_module.pending_state_uids = lambda fight: pending.get()
        replay_module = ModuleType("wakfu_server.combat.combat_event_replay")
        replay_module._READ_PASS_CONTEXTS = read_pass
        scope_module = ModuleType("wakfu_server.combat.combat_structural_qf_scope")
        scope_module._FRAMES = frames

        def observe(fight_change=None, runtime_change=None):
            fight = type("FightProbe", (), {})()
            runtime = type("RuntimeProbe", (), {})()
            fight._resolution_depth = 0
            fight.native_delay_queue = {"entries": {}}
            fight.actors = {}
            runtime.pending = []
            runtime.awaiting_ack = None
            runtime._native_delivery_depth = 0
            if fight_change is not None:
                fight_change(fight)
            if runtime_change is not None:
                runtime_change(runtime)
            detail = []
            self.assertFalse(module._quiescent(fight, runtime, diagnostic=detail))
            self.assertEqual(len(detail), 1)
            return detail[0][0]

        def pending_restoration_actor(fight):
            actor = type("ActorProbe", (), {})()
            actor.native_death_status = {"pending_restoration": True}
            fight.actors = {1: actor}

        modules = {
            "wakfu_server.combat.combat_pending_state": pending_module,
            "wakfu_server.combat.combat_event_replay": replay_module,
            "wakfu_server.combat.combat_structural_qf_scope": scope_module,
        }
        with patch.dict(sys.modules, modules):
            checks = [
                (
                    observe(
                        runtime_change=lambda value: setattr(
                            value, "awaiting_ack", True
                        )
                    ),
                    "runtime.awaiting_ack",
                ),
                (
                    observe(
                        runtime_change=lambda value: setattr(value, "pending", [1])
                    ),
                    "runtime.pending",
                ),
                (
                    observe(
                        fight_change=lambda value: setattr(
                            value, "_resolution_depth", 1
                        )
                    ),
                    "_resolution_depth",
                ),
                (
                    observe(
                        runtime_change=lambda value: setattr(
                            value, "_native_delivery_depth", 1
                        )
                    ),
                    "runtime._native_delivery_depth",
                ),
            ]
            token = pending.set(frozenset((9,)))
            try:
                checks.append((observe(), "pending_state_uids"))
            finally:
                pending.reset(token)
            token = read_pass.set((object(),))
            try:
                checks.append((observe(), "_READ_PASS_CONTEXTS"))
            finally:
                read_pass.reset(token)
            token = frames.set((object(),))
            try:
                checks.append((observe(), "_FRAMES"))
            finally:
                frames.reset(token)
            checks.extend(
                [
                    (
                        observe(
                            fight_change=lambda value: setattr(
                                value, "native_delay_queue", []
                            )
                        ),
                        "native_delay_queue",
                    ),
                    (
                        observe(
                            fight_change=lambda value: setattr(
                                value, "native_delay_queue", {"entries": [1]}
                            )
                        ),
                        "native_delay_queue.entries",
                    ),
                    (
                        observe(fight_change=pending_restoration_actor),
                        "actor.native_death_status.pending_restoration",
                    ),
                ]
            )
        for actual, expected in checks:
            self.assertEqual(actual, expected)

        authority_module = ModuleType(
            "wakfu_server.combat.combat_retained_gc_authority"
        )
        authority_module._FIELDS = (
            "stats_serializer",
            "runtime_stats_serializer",
            "turn_end_provider",
            "turn_start_provider",
            "expiration_runtime_factory",
            "clock",
        )
        authority_module._NativeCallbacks = type("NativeCallbacks", (), {})
        expiration_module = ModuleType("wakfu_server.combat.combat_expiration_provider")
        expiration_module.OwnedExpirationFactory = type(
            "OwnedExpirationFactory", (), {}
        )
        callback_runtime = type("RuntimeProbe", (), {})()
        callback_runtime._retained_gc_callbacks = None
        callback_runtime.stats_serializer = object()
        callback_runtime.runtime_stats_serializer = None
        callback_runtime.turn_end_provider = None
        callback_runtime.turn_start_provider = None
        callback_runtime.expiration_runtime_factory = None
        callback_runtime.clock = time.monotonic
        with patch.dict(
            sys.modules,
            {
                authority_module.__name__: authority_module,
                expiration_module.__name__: expiration_module,
            },
        ):
            self.assertEqual(
                module._native_callback_mismatch(callback_runtime), "stats_serializer"
            )


if __name__ == "__main__":
    unittest.main()
