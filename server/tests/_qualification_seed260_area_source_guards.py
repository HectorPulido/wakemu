"""Refresh the manifest-proven area-source route and its four focused guards."""
import importlib, unittest
from _qualification_resumed_scopes import _refresh_function


def qualify():
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_area_seed_source")
    )
    for name in ("_requires_area_source", "_activate"):
        _refresh_function(
            "wakfu_server.combat_effect_area_events",
            name,
            classname="NativeAreaEventRuntime",
            preserve_aliases=True,
        )
    module = importlib.reload(
        importlib.import_module("test_combat_encounter_area_seed_source")
    )
    return unittest.defaultTestLoader.loadTestsFromName(
        "EncounterAreaSeedSourceTests", module
    )
