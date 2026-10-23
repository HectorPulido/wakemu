"""Load the complete owned-resource route and publication without native reloads."""
import importlib
from wakfu_server import resource_collect, planting
from wakfu_server.objectives import (
    environmental_storage,
    environmental_service,
    environmental_world,
)

for module in (
    resource_collect,
    planting,
    environmental_storage,
    environmental_service,
    environmental_world,
):
    importlib.reload(module)
