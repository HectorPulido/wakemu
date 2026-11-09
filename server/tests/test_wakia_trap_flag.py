"""The trap forecast remains opt-in at World startup."""
import os
from pathlib import Path
import unittest
from types import SimpleNamespace as NS
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
BACKEND_SELECTION = (
    ROOT / "wakfu_server/wakia_bridge/wakfu_ai/bridge/backend_selection.py"
)
MODULE_NAME = "wakfu_server.wakia_bridge.wakfu_ai.bridge.backend_selection"
MODULE_PACKAGE = "wakfu_server.wakia_bridge.wakfu_ai.bridge"


def execute_selection(flag):
    calls = []
    modules = NS(
        jondo_trap_forecast=NS(start_worker=lambda: calls.append("forecast")),
        jondo_trap_prepare=NS(start_worker=lambda: calls.append("prepare")),
    )
    import builtins

    real_import = builtins.__import__
    attempted = []

    def import_hook(name, globals=None, locals=None, fromlist=(), level=0):
        if level == 1 and "jondo_trap_forecast" in fromlist:
            attempted.append(tuple(fromlist))
            return modules
        return real_import(name, globals, locals, fromlist, level)

    env = dict(os.environ)
    env.pop("WAKIA_EXPERIMENTAL_TRAP_FORECAST", None)
    if flag is not None:
        env["WAKIA_EXPERIMENTAL_TRAP_FORECAST"] = flag
    namespace = {"__name__": MODULE_NAME, "__package__": MODULE_PACKAGE}
    with patch.dict(os.environ, env, clear=True), patch.object(
        builtins, "__import__", side_effect=import_hook
    ):
        exec(
            compile(BACKEND_SELECTION.read_text(), str(BACKEND_SELECTION), "exec"),
            namespace,
        )
    return calls, attempted


class TrapForecastFlagTests(unittest.TestCase):
    def test_default_and_non_one_values_do_not_import_or_start_workers(self):
        for value in (None, "0", "true", ""):
            with self.subTest(value=value):
                calls, attempted = execute_selection(value)
                self.assertEqual(calls, [])
                self.assertEqual(attempted, [])

    def test_explicit_experimental_flag_starts_both_workers_once(self):
        calls, attempted = execute_selection("1")
        self.assertEqual(calls, ["forecast", "prepare"])
        self.assertEqual(attempted, [("jondo_trap_forecast", "jondo_trap_prepare")])


if __name__ == "__main__":
    unittest.main()
