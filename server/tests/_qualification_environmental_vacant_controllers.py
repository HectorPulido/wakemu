"""Reload just guarded by-ID controllers and their extended vacancy fixture."""
import importlib
from wakfu_server.objectives import environmental_storage
import test_environmental_active_maps

importlib.reload(environmental_storage)
importlib.reload(test_environmental_active_maps)
