import os
from pathlib import Path
import subprocess
import sys
import unittest


class CatalogGCBootstrapTests(unittest.TestCase):
    def test_published_startup_validates_four_handles_without_eager_heap_or_fallback(
        self,
    ):
        from types import SimpleNamespace
        from unittest.mock import patch
        from wakfu_server import catalog_gc_bootstrap as bootstrap
        from wakfu_server.combat_static_catalogs import CompiledEffects

        variants = ("player", "npc_imported", "npc_baseline", "weapon")
        with patch.dict(os.environ, {"WAKFU_ENABLE_COMBAT_TEST": "1"}), patch.object(
            CompiledEffects,
            "from_published",
            side_effect=lambda variant: SimpleNamespace(effects={"1": variant}),
        ) as handles, patch.object(bootstrap.runpy, "run_path") as run, patch.object(
            bootstrap,
            "freeze_startup_heap",
            side_effect=AssertionError("eager heap freeze"),
        ), patch.object(
            bootstrap, "_prewarm", side_effect=AssertionError("eager prewarm")
        ), patch(
            "builtins.print"
        ):
            bootstrap.main()
            self.assertEqual(
                [call.args[0] for call in handles.call_args_list], list(variants)
            )
            run.assert_called_once_with(
                str(
                    Path(bootstrap.__file__).resolve().parents[2]
                    / "local_game_server.py"
                ),
                run_name="__main__",
            )
            handles.reset_mock()
            run.reset_mock()
            handles.side_effect = RuntimeError("missing exact publication")
            with self.assertRaisesRegex(RuntimeError, "missing exact publication"):
                bootstrap.main()
            run.assert_not_called()
            with patch.dict(os.environ, {"WAKFU_ENABLE_COMBAT_TEST": "0"}):
                handles.reset_mock()
                bootstrap.main()
                handles.assert_not_called()
                run.assert_called_once()

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
