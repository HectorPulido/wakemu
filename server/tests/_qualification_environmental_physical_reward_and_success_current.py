"""Two focused publication regressions in the existing central runner."""
import importlib

for name in (
    "wakfu_server.objectives.environmental_service",
    "wakfu_server.objectives.environmental_world",
    "test_environmental_reward_inventory_publication",
    "test_environmental_world_publication",
):
    importlib.reload(importlib.import_module(name))
