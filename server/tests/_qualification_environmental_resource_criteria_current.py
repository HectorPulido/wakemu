import importlib
from wakfu_server.objectives import (
    environmental_resource_actions,
    environmental_resource_population,
)

for module in (environmental_resource_actions, environmental_resource_population):
    importlib.reload(module)
