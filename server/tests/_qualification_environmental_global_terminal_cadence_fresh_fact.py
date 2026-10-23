"""Use the current gameplay class without reloading production fact producers."""
import importlib
from wakfu_server.objectives import environmental_schedule

importlib.reload(environmental_schedule)
import test_environmental_durable_lifecycle

importlib.reload(test_environmental_durable_lifecycle)
import test_environmental_regional_schedule

importlib.reload(test_environmental_regional_schedule)
