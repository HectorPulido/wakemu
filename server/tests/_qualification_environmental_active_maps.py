"""Use new live-map guards and actual presence fixtures; retain native catalogs."""
import importlib
from wakfu_server import world, planting
from wakfu_server.objectives import (
    environmental_presence,
    environmental_gameplay,
    environmental_storage,
    environmental_service,
    environmental_world,
)

# Reload edited facts before their fixture import bindings; native catalogs remain cached.
for module in (
    world,
    environmental_gameplay,
    environmental_storage,
    environmental_service,
    environmental_world,
    planting,
):
    importlib.reload(module)
import test_environmental_durable_lifecycle, test_environmental_ranking, test_environmental_gameplay, test_environmental_world_publication

for module in (
    test_environmental_durable_lifecycle,
    test_environmental_ranking,
    test_environmental_gameplay,
    test_environmental_world_publication,
):
    importlib.reload(module)
