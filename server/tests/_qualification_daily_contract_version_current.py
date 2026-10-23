import importlib

for name in (
    "wakfu_server.objectives.environmental_recurring_storage",
    "test_recurring_daily_hunter_backend",
):
    importlib.reload(importlib.import_module(name))
