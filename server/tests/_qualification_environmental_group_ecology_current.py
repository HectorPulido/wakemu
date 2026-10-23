import importlib
from wakfu_server import (
    ecology_population,
    monster_reproduction,
    monster_population_cleanup,
    monster_removal_ecology,
    monster_active_clocks,
    monster_population_capacity,
    monster_harvest_ecology,
)

for module in (
    ecology_population,
    monster_reproduction,
    monster_population_cleanup,
    monster_removal_ecology,
    monster_active_clocks,
    monster_population_capacity,
    monster_harvest_ecology,
):
    importlib.reload(module)
