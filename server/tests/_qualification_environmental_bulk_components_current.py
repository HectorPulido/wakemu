import importlib
from wakfu_server.objectives import environmental_group_population
from wakfu_server import treasure_chests

for module in (environmental_group_population, treasure_chests):
    importlib.reload(module)
import test_environmental_owned_group_population

importlib.reload(test_environmental_owned_group_population)
