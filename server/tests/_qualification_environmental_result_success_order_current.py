"""One new earned-result presentation regression, no catalog or database load."""
import importlib

for name in (
    "wakfu_server.objectives.environmental_world",
    "test_environmental_world_publication",
):
    importlib.reload(importlib.import_module(name))
