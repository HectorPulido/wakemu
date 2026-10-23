import importlib

for name in (
    "wakfu_server.resource_collect",
    "wakfu_server.objectives.environmental_service",
    "wakfu_server.objectives.environmental_world",
):
    importlib.reload(importlib.import_module(name))

importlib.reload(importlib.import_module("test_environmental_company_result_delivery"))
