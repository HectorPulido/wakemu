"""Refresh just the explicit pre-start automatic-binding fence."""
import importlib
from wakfu_server.objectives import environmental_groups
import test_environmental_group_wins

importlib.reload(environmental_groups)
importlib.reload(test_environmental_group_wins)
