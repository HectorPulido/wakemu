"""Adopt only new binding code and refresh edited fact/profile fixture imports."""
import importlib
from wakfu_server.objectives import environmental_runtime, environmental_gameplay

for module in (environmental_runtime, environmental_gameplay):
    importlib.reload(module)
import test_environmental_gameplay

importlib.reload(test_environmental_gameplay)
