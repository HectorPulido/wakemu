"""Load the new concurrent regression without repeating qualified fixtures."""
import importlib
import test_environmental_durable_lifecycle


class EnvironmentalConcurrencyQualification(
    importlib.reload(
        test_environmental_durable_lifecycle
    ).EnvironmentalDurableLifecycleTests
):
    pass
