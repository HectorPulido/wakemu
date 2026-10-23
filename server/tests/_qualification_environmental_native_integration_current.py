import importlib
from wakfu_server.objectives import (
    environmental_storage,
    environmental_service,
    environmental_world,
)

for module in (environmental_storage, environmental_service, environmental_world):
    importlib.reload(module)
import test_environmental_regional_schedule

importlib.reload(test_environmental_regional_schedule)
