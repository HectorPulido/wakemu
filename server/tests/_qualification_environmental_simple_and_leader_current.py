import importlib
from wakfu_server.objectives import (
    environmental_storage,
    environmental_service,
    environmental_evaluation,
    environmental_native_variables,
)

for module in (
    environmental_storage,
    environmental_service,
    environmental_evaluation,
    environmental_native_variables,
):
    importlib.reload(module)
import test_environmental_native_variables

importlib.reload(test_environmental_native_variables)
