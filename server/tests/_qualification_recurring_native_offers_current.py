import importlib

for name in (
    "wakfu_server.objectives.environmental_recurring_contracts",
    "wakfu_server.objectives.environmental_recurring_offers",
    "wakfu_server.objectives.environmental_recurring_storage",
    "test_environmental_recurring_contracts",
    "test_recurring_hunter_backend",
):
    importlib.reload(importlib.import_module(name))
