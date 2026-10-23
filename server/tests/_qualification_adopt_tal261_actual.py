"""Adopt the formally admitted event population policy without class replacement."""
import importlib, json, unittest
from pathlib import Path
from _qualification_resumed_scopes import _refresh_function


def refresh():
    importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_event_population")
    )
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    _refresh_function(
        "wakfu_server.combat_effect_runtime",
        "__call__",
        classname="NativeEffectRuntimeFactory",
        preserve_aliases=True,
    )
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    factory = importlib.import_module(
        "wakfu_server.combat_effect_runtime"
    ).NativeEffectRuntimeFactory
    assert "freeze_event_population_policy" in roles.bind_roles.__code__.co_names
    assert "permits_event_group_population" in factory.__call__.__code__.co_names
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/tal261-loaded-admission-and-factory-proof.json"
    ).write_text(
        json.dumps(
            dict(
                role_names=roles.bind_roles.__code__.co_names,
                factory_names=factory.__call__.__code__.co_names,
            ),
            indent=2,
        )
    )
    return unittest.TestSuite()
