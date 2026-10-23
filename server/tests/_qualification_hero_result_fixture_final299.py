import importlib

for name in (
    "wakfu_server.resource_collect",
    "wakfu_server.objectives.environmental_service",
    "wakfu_server.objectives.environmental_world",
    "test_environmental_company_result_delivery",
):
    importlib.reload(importlib.import_module(name))
