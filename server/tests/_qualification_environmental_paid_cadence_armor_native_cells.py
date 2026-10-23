"""Refresh the three changed focused fixtures without resetting native classes."""
import importlib
from wakfu_server import combat_armor
from wakfu_server.objectives import environmental_schedule

importlib.reload(combat_armor)
importlib.reload(environmental_schedule)
import test_environmental_durable_lifecycle

importlib.reload(test_environmental_durable_lifecycle)
import test_environmental_regional_schedule
import test_combat_armor
import test_environmental_owned_combat_route

for module in (
    test_environmental_regional_schedule,
    test_combat_armor,
    test_environmental_owned_combat_route,
):
    importlib.reload(module)
