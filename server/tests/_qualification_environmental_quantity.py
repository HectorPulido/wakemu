"""Load the quantity-boundary regression in the existing native test process."""
import importlib
from wakfu_server.objectives import environmental_storage
import test_environmental_durable_lifecycle

importlib.reload(environmental_storage)


class EnvironmentalQuantityQualification(
    importlib.reload(
        test_environmental_durable_lifecycle
    ).EnvironmentalDurableLifecycleTests
):
    pass
