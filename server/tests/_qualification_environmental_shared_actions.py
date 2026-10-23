"""Reload only shared environmental action settlement and its affected fixtures."""
import importlib
from wakfu_server.objectives import environmental_gameplay, environmental_storage
from wakfu_server.achievements import combat_adapter

for module in (environmental_gameplay, environmental_storage, combat_adapter):
    importlib.reload(module)
import test_environmental_gameplay, test_environmental_group_wins, test_environmental_durable_lifecycle

for module in (
    test_environmental_gameplay,
    test_environmental_group_wins,
    test_environmental_durable_lifecycle,
):
    importlib.reload(module)
