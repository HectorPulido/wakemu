"""One clock regression; retain the existing warm native catalog and pools."""
import importlib

for name in (
    "wakfu_server.objectives.environmental_world",
    "test_environmental_world_publication",
):
    importlib.reload(importlib.import_module(name))
