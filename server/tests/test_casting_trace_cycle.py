"""Trace adapter preserves custom delegation without retaining hook owners."""
import gc
import unittest
import weakref
from wakfu_server.combat_casting_eligibility import (
    NativeCastingFlags,
    native_casting_eligibility,
)
from wakfu_server.combat_conditions import UnknownCondition


class DynamicHooks:
    def __init__(self, mode, calls):
        self.mode, self.calls = mode, calls

    def __getattr__(self, name):
        self.calls.append(("get", name))
        if name != "container_present":
            raise AssertionError("Early rejection consumed a later hook")
        if self.mode == "noncallable":
            return False
        mode, calls = self.mode, self.calls

        def consume():
            calls.append(("call", name))
            if mode == "error":
                raise ValueError("native hook failure")
            return False

        return consume


class CastingTraceCycleTests(unittest.TestCase):
    def test_custom_hook_trace_success_error_and_noncallable_release(self):
        enabled = gc.isenabled()
        gc.disable()
        try:
            for mode in ("success", "error", "noncallable"):
                with self.subTest(mode=mode):
                    calls, trace = [], []
                    hooks = DynamicHooks(mode, calls)
                    reference = weakref.ref(hooks)
                    if mode == "success":
                        self.assertEqual(
                            native_casting_eligibility(
                                hooks, NativeCastingFlags(), trace=trace
                            ),
                            "twF",
                        )
                        self.assertEqual(
                            trace,
                            [
                                dict(
                                    stage="container_present", arguments=[], value=False
                                ),
                                dict(stage="result", value="twF"),
                            ],
                        )
                    else:
                        try:
                            native_casting_eligibility(
                                hooks, NativeCastingFlags(), trace=trace
                            )
                        except ValueError as error:
                            self.assertIs(error.native_casting_trace, trace)
                            if mode == "error":
                                self.assertEqual(
                                    trace,
                                    [
                                        dict(
                                            stage="container_present",
                                            arguments=[],
                                            error="native hook failure",
                                        )
                                    ],
                                )
                            else:
                                self.assertIsInstance(error, UnknownCondition)
                                self.assertEqual(trace, [])
                        else:
                            self.fail("Missing native hook rejection")
                    self.assertEqual(
                        calls,
                        [("get", "container_present")]
                        + (
                            []
                            if mode == "noncallable"
                            else [("call", "container_present")]
                        ),
                    )
                    del hooks
                    self.assertIsNone(
                        reference(),
                        "Trace query must not leave a class/closure retaining hooks",
                    )
        finally:
            if enabled:
                gc.enable()
