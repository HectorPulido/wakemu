"""Refresh the actual global death observer and its two focused callers."""
import importlib
from wakfu_server import combat_death_events

importlib.reload(combat_death_events)
import test_combat_death_events
import test_environmental_owned_combat_route

for module in (test_combat_death_events, test_environmental_owned_combat_route):
    importlib.reload(module)
