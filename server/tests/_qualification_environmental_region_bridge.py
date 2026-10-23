"""Refresh the source-region producer fix and its compact affected contracts."""
import importlib
from wakfu_server.objectives import environmental_gameplay
from wakfu_server.achievements import combat_adapter
import test_environmental_gameplay

for module in (environmental_gameplay, combat_adapter, test_environmental_gameplay):
    importlib.reload(module)
