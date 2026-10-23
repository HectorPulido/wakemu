"""Use current phase code without invalidating native catalog caches."""
import importlib
from wakfu_server.objectives import (
    environmental_runtime,
    environmental_storage,
    environmental_world,
)

for module in (environmental_runtime, environmental_storage, environmental_world):
    importlib.reload(module)
