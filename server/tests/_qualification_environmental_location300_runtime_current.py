import importlib

for name in (
    "wakfu_server.objectives.environmental_location_criteria",
    "wakfu_server.objectives.environmental_schedule",
    "wakfu_server.objectives.environmental_storage",
    "test_environmental_location_criteria",
):
    importlib.reload(importlib.import_module(name))
