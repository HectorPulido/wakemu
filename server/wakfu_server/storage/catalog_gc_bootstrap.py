"""Freeze only the pre-world startup heap; leave gameplay cyclic GC enabled.

CPython cannot freeze selected objects. This module must therefore run before
the world module is imported, before listeners, live registries or workers.
The pinned catalogue generation is intentionally retained until process exit.
"""
import gc
import json
import os
import runpy
import sys
import threading
import time
from pathlib import Path

_completed = False
_LIVE_TYPES = frozenset(
    {
        "Fight",
        "RuntimeMessages",
        "World",
        "Harvests",
        "Plantings",
        "Store",
        "CombatGroups",
        "Groups",
        "SharedCombat",
        "SharedFight",
        "EcologyWorldBridge",
    }
)


def _assert_startup():
    if threading.current_thread() is not threading.main_thread():
        raise RuntimeError("Catalogue heap freeze requires the startup main thread")
    if any(
        name == "local_game_server" or name.endswith(".local_game_server")
        for name in sys.modules
    ):
        raise RuntimeError("World was imported before catalogue heap freeze")
    if any(thread is not threading.main_thread() for thread in threading.enumerate()):
        raise RuntimeError("Workers exist before catalogue heap freeze")
    if not gc.isenabled():
        raise RuntimeError("Catalogue heap freeze requires cyclic GC enabled")
    for value in gc.get_objects():
        kind = type(value)
        module = getattr(kind, "__module__", None)
        if (
            isinstance(module, str)
            and module.startswith("wakfu_server")
            and (
                kind.__name__ in _LIVE_TYPES
                or (
                    kind.__module__ == "wakfu_server.combat_shared"
                    and kind.__name__ in {"Registry", "Session"}
                )
            )
        ):
            raise RuntimeError("Live game state exists before catalogue heap freeze")


def freeze_startup_heap(prewarm, cleanup):
    """Warm static authority, release I/O roots, collect, then seal startup GC.

    Callbacks are supplied to allow isolated subprocess regression tests.
    Cleanup must close and discard every temporary database/Redis singleton.
    A failed guard aborts startup; it never freezes an already-running world.
    """
    global _completed
    if _completed:
        raise RuntimeError("Catalogue heap freeze already completed")
    _assert_startup()
    started = time.monotonic()
    gc.disable()
    try:
        details = prewarm()
    finally:
        gc.enable()
        cleanup()
    _assert_startup()
    collected = gc.collect()
    _assert_startup()
    gc.freeze()
    _completed = True
    return dict(
        details=details,
        collected=collected,
        frozen_objects=gc.get_freeze_count(),
        elapsed_ms=round((time.monotonic() - started) * 1000, 3),
        gc_enabled=gc.isenabled(),
    )


def _prewarm():
    from wakfu_server.combat_module_loading import preload_combat_modules
    from wakfu_server.combat_server_spell import prewarm_runtime_catalogs

    return dict(**preload_combat_modules(), **prewarm_runtime_catalogs())


def _cleanup():
    from wakfu_server import native_catalog

    if native_catalog._database.cache_info().currsize:
        database = native_catalog._database()
        try:
            database.close()
        finally:
            native_catalog._database.cache_clear()
    if native_catalog._redis.cache_info().currsize:
        client = native_catalog._redis()
        try:
            client.close()
        finally:
            native_catalog._redis.cache_clear()


def main():
    if (
        os.environ.get("WAKFU_ENABLE_COMBAT_TEST") == "1"
        and os.environ.get("WAKFU_CATALOG_GC_FREEZE", "1") == "1"
    ):
        result = freeze_startup_heap(_prewarm, _cleanup)
        print(
            json.dumps(dict(event="catalog_startup_heap_frozen", **result)), flush=True
        )
    world = Path(__file__).resolve().parents[2] / "local_game_server.py"
    runpy.run_path(str(world), run_name="__main__")


if __name__ == "__main__":
    main()
