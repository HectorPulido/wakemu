"""Reload only actual group/fact integration and its compact affected fixtures."""
import importlib
from wakfu_server.objectives import environmental_gameplay, environmental_storage
from wakfu_server.achievements import combat_adapter

for module in (environmental_gameplay, environmental_storage, combat_adapter):
    importlib.reload(module)
import test_environmental_gameplay

importlib.reload(test_environmental_gameplay)
