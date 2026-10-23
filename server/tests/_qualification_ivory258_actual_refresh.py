"""Adopt the formally admitted recipient policy for its sole actual caller."""
import importlib, unittest
from _qualification_resumed_scopes import _refresh_function


def qualify():
    tal = importlib.import_module("test_talkasha_paid_native_rykaon")
    assert tal.TAL_ACTUAL_CHECKPOINT is None
    policy = importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_recipient_binding")
    )
    policy._version.cache_clear()
    _refresh_function(
        "wakfu_server.combat_encounter_roles", "bind_roles", preserve_aliases=True
    )
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    assert (
        "freeze_encounter_recipient_binding_policy"
        in roles.bind_roles.__code__.co_names
    )
    for name in ("__init__", "candidate_invocations"):
        _refresh_function(
            "wakfu_server.combat_effect_resolver",
            name,
            classname="NativeEffectResolver",
            preserve_aliases=True,
        )
    _refresh_function(
        "wakfu_server.combat_effect_runtime",
        "__call__",
        classname="NativeEffectRuntimeFactory",
        preserve_aliases=True,
    )
    factory = importlib.import_module(
        "wakfu_server.combat_effect_runtime"
    ).NativeEffectRuntimeFactory
    assert (
        "preserve_explicit_recipient" in factory.__call__.__code__.co_consts
        or "permits_native_recipient_binding" in factory.__call__.__code__.co_names
    )
    importlib.reload(importlib.import_module("test_ogrest_reconstructed_native_phase"))
    return unittest.TestSuite()
