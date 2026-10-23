import importlib

for name in (
    "wakfu_server.objectives.environmental_group_progress",
    "test_environmental_random_group_lifecycle",
):
    importlib.reload(importlib.import_module(name))
