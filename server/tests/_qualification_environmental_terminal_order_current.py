import importlib
from wakfu_server.objectives import environmental_world, environmental_service

for module in (environmental_world, environmental_service):
    importlib.reload(module)
import test_environmental_world_publication

importlib.reload(test_environmental_world_publication)
