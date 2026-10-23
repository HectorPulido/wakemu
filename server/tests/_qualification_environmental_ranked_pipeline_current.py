import importlib
from wakfu_server.objectives import (
    environmental_storage,
    environmental_service,
    environmental_evaluation,
)

for module in (environmental_storage, environmental_service, environmental_evaluation):
    importlib.reload(module)
