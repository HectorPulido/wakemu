"""Refresh only the admitted scoped end ordering and its actual cycle-five caller."""
import importlib
import unittest
from _qualification_resumed_scopes import _refresh_function


def refresh():
    module = importlib.reload(
        importlib.import_module("wakfu_server.combat_encounter_turn_end_order")
    )
    module._version.cache_clear()
    roles = importlib.import_module("wakfu_server.combat_encounter_roles")
    assert "freeze_turn_end_order_policy" in roles.bind_roles.__code__.co_names
    assert (
        "freeze_encounter_recipient_binding_policy"
        not in roles.bind_roles.__code__.co_names
    )
    import _qualification_turn_end_deep_wrapper_refresh as turn_end

    turn_end.refresh()
    importlib.reload(importlib.import_module("test_rushu_native_party_phase_one"))
    return unittest.TestSuite()
