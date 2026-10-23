import importlib

for name in (
    "wakfu_server.objectives.environmental_resource_stage",
    "wakfu_server.objectives.environmental_resource_population",
    "wakfu_server.objectives.environmental_resource_actions",
    "test_environmental_declared_resource_stages",
):
    importlib.reload(importlib.import_module(name))
