"""Apply the released narrow844 operand route and preserve factory alias identity."""
import importlib, inspect, json, unittest
from pathlib import Path
from _qualification_resumed_scopes import _refresh_function


def qualify():
    recipe = importlib.import_module("test_ombrage_native_paid_clock")
    assert recipe.OMBRAGE_ACTUAL_CHECKPOINT is None
    helper = importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_area_seed_source")
    )
    assert hasattr(helper, "seed_program_level_source")
    groups = importlib.import_module("wakfu_server.combat_state_level_group")
    factory = importlib.import_module("wakfu_server.combat_effect_runtime")
    original = groups.runtime_child_level
    _refresh_function(
        "wakfu_server.combat_state_level_group",
        "runtime_child_level",
        preserve_aliases=True,
    )
    assert groups.runtime_child_level is original
    factory.native_state_group_level = groups.runtime_child_level
    assert factory.native_state_group_level is groups.runtime_child_level
    assert groups.runtime_child_level.__kwdefaults__["level_source_resolver"] is None
    for name in ("_requires_area_source", "_activate"):
        _refresh_function(
            "wakfu_server.combat_effect_area_events",
            name,
            classname="NativeAreaEventRuntime",
            preserve_aliases=True,
        )
    events = importlib.import_module(
        "wakfu_server.combat_effect_area_events"
    ).NativeAreaEventRuntime
    assert (
        "seed_program_requires_area_source"
        not in events._requires_area_source.__code__.co_names
    )
    assert list(inspect.signature(events._requires_area_source).parameters) == [
        "self",
        "reference",
    ]
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/rushu844-coherent-loaded-alias-operand-and-event-source-proof.json"
    ).write_text(
        json.dumps(
            dict(
                alias_identity=True,
                group_signature=str(inspect.signature(groups.runtime_child_level)),
                group_names=groups.runtime_child_level.__code__.co_names,
                requires_names=events._requires_area_source.__code__.co_names,
                activate_names=events._activate.__code__.co_names,
            ),
            indent=2,
        )
    )
    module = importlib.reload(
        importlib.import_module("test_combat_encounter_area_seed_source")
    )
    return unittest.defaultTestLoader.loadTestsFromName(
        "EncounterAreaSeedSourceTests", module
    )
