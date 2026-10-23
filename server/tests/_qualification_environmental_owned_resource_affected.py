"""Load the owned-growth exclusion and refresh only affected fixture imports."""
import importlib
from wakfu_server import planting_runtime

importlib.reload(planting_runtime)
import test_environmental_company, test_environmental_active_maps, test_environmental_durable_lifecycle

for module in (
    test_environmental_company,
    test_environmental_active_maps,
    test_environmental_durable_lifecycle,
):
    importlib.reload(module)
