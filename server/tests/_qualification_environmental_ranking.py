"""Load only the declared ranking addition over the retained source catalogs."""
import importlib
from wakfu_server.objectives import environmental_runtime, environmental_storage

for module in (environmental_runtime, environmental_storage):
    importlib.reload(module)
