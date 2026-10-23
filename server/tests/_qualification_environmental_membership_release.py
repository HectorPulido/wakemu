"""Adopt the bounded real release consumer without replaying unchanged cases."""
import importlib
from wakfu_server.objectives import environmental_service
import test_environmental_planting_binding

importlib.reload(environmental_service)
importlib.reload(test_environmental_planting_binding)
