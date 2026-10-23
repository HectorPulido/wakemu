"""Refresh exact immutable descriptor normalization and the two affected PGs."""
import importlib, unittest
from _qualification_resumed_scopes import _refresh_function


def qualify():
    _refresh_function(
        "wakfu_server.combat_encounter_recipient_binding",
        "permits_native_recipient_binding",
        preserve_aliases=True,
    )
    importlib.reload(importlib.import_module("test_ogrest_native_recipient_binding"))
    return unittest.defaultTestLoader.loadTestsFromName(
        "test_ogrest_native_recipient_binding.OgrestNativeRecipientBindingTests"
    )
