"""Reload unfinished environmental code only; preserve the shared native heap."""
import importlib

from wakfu_server.objectives import environmental_storage
import test_environmental_durable_lifecycle

importlib.reload(environmental_storage)


class CurrentEnvironmentalQualification(
    importlib.reload(
        test_environmental_durable_lifecycle
    ).EnvironmentalDurableLifecycleTests
):
    pass
