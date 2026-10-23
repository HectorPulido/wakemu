import importlib

for name in (
    "test_daily_hunter_target_compiler",
    "test_recurring_daily_hunter_backend",
    "test_daily_hunter_selection",
):
    importlib.reload(importlib.import_module(name))
