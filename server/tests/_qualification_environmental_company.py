"""Load owned company environmental changes without reloading native catalogs."""
import importlib
from wakfu_server.objectives import (
    environmental_gameplay,
    environmental_service,
    environmental_world,
)

for module in (environmental_gameplay, environmental_service, environmental_world):
    importlib.reload(module)
import test_environmental_gameplay, test_environmental_durable_lifecycle, test_environmental_planting_binding

for module in (
    test_environmental_gameplay,
    test_environmental_durable_lifecycle,
    test_environmental_planting_binding,
):
    importlib.reload(module)
