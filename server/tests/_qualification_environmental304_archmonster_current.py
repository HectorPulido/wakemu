import importlib

for name in (
    "wakfu_server.objectives.environmental_archmonster_geometry",
    "wakfu_server.objectives.environmental_archmonster_runtime",
    "wakfu_server.objectives.environmental_schedule",
    "test_environmental_archmonster_runtime",
):
    importlib.reload(importlib.import_module(name))
