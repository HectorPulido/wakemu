"""Reload the corrected armor slot and the one ordinary-finish regression."""
import importlib
from wakfu_server import combat_armor

importlib.reload(combat_armor)
import test_environmental_owned_combat_route

importlib.reload(test_environmental_owned_combat_route)
