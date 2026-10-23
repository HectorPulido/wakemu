"""Reload only changed rank/context paths and the focused test fact alias."""
import importlib
from wakfu_server.objectives import (
    environmental_evaluation,
    environmental_storage,
    environmental_world,
)

for module in (environmental_evaluation, environmental_storage, environmental_world):
    importlib.reload(module)
import test_environmental_durable_lifecycle

importlib.reload(test_environmental_durable_lifecycle)
import test_environmental_live_competitive_rank

importlib.reload(test_environmental_live_competitive_rank)
