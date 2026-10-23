import importlib
import test_environmental_active_maps, test_environmental_durable_lifecycle, test_environmental_company

for module in (
    test_environmental_active_maps,
    test_environmental_durable_lifecycle,
    test_environmental_company,
):
    importlib.reload(module)
