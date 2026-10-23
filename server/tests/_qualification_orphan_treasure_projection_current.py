import importlib
from wakfu_server import declared_treasure_rewards, treasure_chests

for module in (declared_treasure_rewards, treasure_chests):
    importlib.reload(module)
