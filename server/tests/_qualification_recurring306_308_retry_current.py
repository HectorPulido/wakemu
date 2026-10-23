"""Retry only the two affected cases without rebuilding the native catalog."""
import importlib
from wakfu_server import native_catalog

# OrbStack restarted after the warm runner cached these database sockets.
# Check/replenish only that connection pool; retain every release/record cache.
native_catalog._database().pool.check()

for name in (
    "test_recurring_modulox_strict_boss_delta",
    "test_recurring_daily_native_boss_delta",
):
    importlib.reload(importlib.import_module(name))
