import os
from pathlib import Path
import subprocess
import sys
import unittest


class CatalogGCBootstrapTests(unittest.TestCase):
    def test_startup_freezes_once_and_passes_receipt_before_world_import(self):
        from unittest.mock import patch
        from wakfu_server import catalog_gc_bootstrap as bootstrap

        receipt = dict(
            details=dict(combat_modules=1, effect_definitions=2),
            elapsed_ms=3.0,
            gc_enabled=True,
        )
        with patch.dict(os.environ, {"WAKFU_ENABLE_COMBAT_TEST": "1"}), patch.object(
            bootstrap, "freeze_startup_heap", return_value=receipt
        ) as freeze, patch.object(bootstrap.runpy, "run_path") as run, patch(
            "builtins.print"
        ):
            bootstrap.main()
            freeze.assert_called_once_with(bootstrap._prewarm, bootstrap._cleanup)
            run.assert_called_once_with(
                str(
                    Path(bootstrap.__file__).resolve().parents[2]
                    / "local_game_server.py"
                ),
                run_name="__main__",
                init_globals={"_COMBAT_STARTUP_PREWARM": receipt},
            )
            freeze.reset_mock()
            run.reset_mock()
            freeze.side_effect = RuntimeError("unsafe startup boundary")
            with self.assertRaisesRegex(RuntimeError, "unsafe startup boundary"):
                bootstrap.main()
            run.assert_not_called()
            with patch.dict(os.environ, {"WAKFU_ENABLE_COMBAT_TEST": "0"}):
                freeze.reset_mock()
                bootstrap.main()
                freeze.assert_not_called()
                run.assert_called_once_with(
                    str(
                        Path(bootstrap.__file__).resolve().parents[2]
                        / "local_game_server.py"
                    ),
                    run_name="__main__",
                    init_globals={},
                )

    def test_world_consumes_receipt_or_warms_direct_entry_and_still_seals_ai(self):
        # Execute only the actual startup wiring block: importing World itself
        # would create serving stores/registries. Actual prewarm is covered by
        # the isolated native bootstrap proof, not these mocked I/O providers.
        import ast
        import time
        from types import SimpleNamespace
        from unittest.mock import Mock, patch

        path = Path(
            os.environ.get(
                "WAKFU_TEST_WORLD_SOURCE",
                Path(__file__).resolve().parents[1] / "local_game_server.py",
            )
        )
        tree = ast.parse(path.read_text())
        main = next(
            node
            for node in tree.body
            if isinstance(node, ast.FunctionDef) and node.name == "main"
        )
        block = next(
            node
            for node in main.body
            if isinstance(node, ast.If)
            and isinstance(node.test, ast.Name)
            and node.test.id == "COMBAT_TEST"
        )
        code = compile(
            ast.fix_missing_locations(ast.Module(body=[block], type_ignores=[])),
            str(path),
            "exec",
        )
        receipt = dict(
            details=dict(combat_modules=7, effect_definitions=11), elapsed_ms=9.0
        )
        for prewarmed in (None, receipt):
            preload = Mock(return_value=dict(combat_modules=7))
            warm = Mock(return_value=dict(effect_definitions=11))
            record = Mock()
            namespace = dict(
                COMBAT_TEST=True, time=time, os=os, record=record, __file__=str(path)
            )
            if prewarmed is not None:
                namespace["_COMBAT_STARTUP_PREWARM"] = prewarmed
            modules = {
                "wakfu_server.combat_module_loading": SimpleNamespace(
                    preload_combat_modules=preload
                ),
                "wakfu_server.combat_server_spell": SimpleNamespace(
                    prewarm_runtime_catalogs=warm
                ),
            }
            with patch.dict(sys.modules, modules), patch("subprocess.run") as seal:
                exec(code, namespace)
            self.assertEqual(preload.call_count, 1 if prewarmed is None else 0)
            self.assertEqual(warm.call_count, 1 if prewarmed is None else 0)
            seal.assert_called_once()
            self.assertEqual(seal.call_args.args[0][-1], "--seal")
            self.assertTrue(seal.call_args.kwargs["check"])
            self.assertEqual(record.call_args.kwargs["combat_modules"], 7)
            self.assertEqual(record.call_args.kwargs["effect_definitions"], 11)
            self.assertNotIn("_COMBAT_STARTUP_PREWARM", namespace)

    def run_case(self, source):
        env = dict(os.environ, PYTHONPATH=str(Path(__file__).resolve().parents[1]))
        source = "import gc\ninitial_frozen = gc.get_freeze_count()\n" + source
        result = subprocess.run(
            [sys.executable, "-c", source],
            env=env,
            capture_output=True,
            text=True,
            timeout=15,
        )
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)

    def test_static_heap_frozen_future_gameplay_cycles_still_collect(self):
        self.run_case(
            """
import gc, weakref
from wakfu_server.catalog_gc_bootstrap import freeze_startup_heap
static = []
cleanup = []
Odd = type('Odd', (), {'__module__': property(lambda self: None)})
odd = Odd()
result = freeze_startup_heap(lambda: static.extend([[1,2,3]]) or {}, lambda: cleanup.append(True))
assert result['frozen_objects'] > 0 and result['gc_enabled'] and cleanup
class FutureGameObject: pass
actor = FutureGameObject(); actor.self = actor
reference = weakref.ref(actor)
static.append(actor)
del actor
static.pop()
gc.collect()
assert reference() is None
assert static == [[1,2,3]]
"""
        )

    def test_world_import_rejected_before_prewarm_or_freeze(self):
        self.run_case(
            """
import gc, sys, types
from wakfu_server.catalog_gc_bootstrap import freeze_startup_heap
sys.modules['local_game_server'] = types.ModuleType('local_game_server')
try: freeze_startup_heap(lambda: (_ for _ in ()).throw(AssertionError()), lambda: None)
except RuntimeError: pass
else: raise AssertionError('world import accepted')
assert gc.get_freeze_count() == initial_frozen and gc.isenabled()
"""
        )

    def test_live_fight_created_by_prewarm_rejected_cleanup_runs(self):
        self.run_case(
            """
import gc
from wakfu_server.catalog_gc_bootstrap import freeze_startup_heap
Fight = type('Fight', (), {'__module__': 'wakfu_server.combat_state'})
live = []; cleanup = []
try: freeze_startup_heap(lambda: live.append(Fight()) or {}, lambda: cleanup.append(True))
except RuntimeError: pass
else: raise AssertionError('live fight accepted')
assert cleanup and gc.get_freeze_count() == initial_frozen
"""
        )

    def test_prewarm_failure_does_not_freeze_and_releases_resources(self):
        self.run_case(
            """
import gc
from wakfu_server.catalog_gc_bootstrap import freeze_startup_heap
cleanup=[]
def fail(): raise ValueError('prewarm')
try: freeze_startup_heap(fail, lambda: cleanup.append(True))
except ValueError: pass
else: raise AssertionError('failure swallowed')
assert cleanup and gc.get_freeze_count() == initial_frozen and gc.isenabled()
"""
        )

    def test_second_freeze_rejected(self):
        self.run_case(
            """
from wakfu_server.catalog_gc_bootstrap import freeze_startup_heap
freeze_startup_heap(lambda: {}, lambda: None)
try: freeze_startup_heap(lambda: {}, lambda: None)
except RuntimeError: pass
else: raise AssertionError('second freeze accepted')
"""
        )
