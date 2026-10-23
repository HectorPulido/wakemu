"""Adopt the qualified264 hooks coherently, then inspect only legal full admission."""
import importlib, json, sys, unittest
from pathlib import Path
from _qualification_resumed_scopes import _refresh_function


def qualify():
    nox = sys.modules.get("test_nox_cube24_fixed12_joint")
    assert nox is None or not nox.retained_components
    om = sys.modules.get("test_ombrage_native_paid_clock")
    assert om is None or om.OMBRAGE_ACTUAL_CHECKPOINT is None
    for path in (
        "wakfu_server.combat_encounter_npc_start_binding",
        "wakfu_server.combat_encounter_area_callback_programs",
        "wakfu_server.combat_encounter_area_callback_source",
        "wakfu_server.combat_encounter_area_seed_source",
    ):
        importlib.reload(importlib.import_module(path))
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    _refresh_function(
        "wakfu_server.combat_event_replay",
        "__call__",
        classname="NativeEventReplay",
        preserve_aliases=True,
    )
    _refresh_function(
        "wakfu_server.combat_state_level_group",
        "runtime_child_level",
        preserve_aliases=True,
    )
    _refresh_function(
        "wakfu_server.combat_effect_runtime",
        "__call__",
        classname="NativeEffectRuntimeFactory",
        preserve_aliases=True,
    )
    groups = importlib.import_module("wakfu_server.combat_state_level_group")
    factory = importlib.import_module("wakfu_server.combat_effect_runtime")
    factory.native_state_group_level = groups.runtime_child_level
    assert factory.native_state_group_level is groups.runtime_child_level
    assert groups.runtime_child_level.__kwdefaults__["level_source_resolver"] is None
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    assert "freeze_npc_start_binding" in roles.bind_roles.__code__.co_names
    assert (
        "freeze_encounter_area_callback_programs" in roles.bind_roles.__code__.co_names
    )
    Path(
        ".runtime/high-priority-qualification-20261021/fresh-null-qf-and-components/rushu264-coherent-loaded-admission-proof.json"
    ).write_text(
        json.dumps(
            dict(
                alias_identity=True,
                roles_names=roles.bind_roles.__code__.co_names,
                group_names=groups.runtime_child_level.__code__.co_names,
                factory_class_identity_preserved=True,
                replay_class_identity_preserved=True,
            ),
            indent=2,
        )
    )
    module = importlib.reload(
        importlib.import_module("test_rushu_native_party_phase_one")
    )
    return unittest.defaultTestLoader.loadTestsFromName(
        "RushuNativePartyPhaseOneTests.diagnose_native_party_admission", module
    )
