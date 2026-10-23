import importlib

for name in (
    "wakfu_server.objectives.environmental_recurring_storage",
    "wakfu_server.objectives.environmental_modulox_contracts",
    "test_recurring_hunter_backend",
    "test_recurring_daily_hunter_backend",
    "test_daily_hunter_selection",
):
    importlib.reload(importlib.import_module(name))
