"""Reload only the affected recurring consumer and three new central cases.

Import this unique helper once; pass the three exact IDs to the runner separately.
No suite is exposed here, so discovery cannot execute the same case twice.
"""
import importlib

for name in (
    "wakfu_server.objectives.environmental_modulox_contracts",
    "wakfu_server.objectives.environmental_recurring_storage",
    "test_recurring_modulox_strict_boss_delta",
    "test_environmental_archmonster_cadence_upgrade",
    "test_recurring_daily_native_boss_delta",
):
    importlib.reload(importlib.import_module(name))
