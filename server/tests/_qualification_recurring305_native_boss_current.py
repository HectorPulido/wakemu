import importlib

for name in (
    "wakfu_server.objectives.environmental_modulox_contracts",
    "wakfu_server.objectives.environmental_recurring_storage",
    "test_recurring_modulox_native_boss_backend",
):
    importlib.reload(importlib.import_module(name))
