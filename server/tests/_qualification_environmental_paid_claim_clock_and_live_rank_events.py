"""Reload only two corrected fixture callers; qualified production stays loaded."""
import importlib
import test_environmental_owned_combat_route
import test_environmental_live_competitive_rank

for module in (
    test_environmental_owned_combat_route,
    test_environmental_live_competitive_rank,
):
    importlib.reload(module)
