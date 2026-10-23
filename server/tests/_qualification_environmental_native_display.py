"""Load the recovered native display contract and its actual signed-rank limit."""
import importlib
from wakfu_server.objectives import environmental_runtime, environmental_results
import test_environmental_native_source_catalog

for module in (
    environmental_runtime,
    environmental_results,
    test_environmental_native_source_catalog,
):
    importlib.reload(module)
