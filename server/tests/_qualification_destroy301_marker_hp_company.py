import importlib

for name in (
    "wakfu_server.combat.combat_monster_world",
    "wakfu_server.objectives.environmental_monster_destroy",
    "wakfu_server.objectives.environmental_company",
    "test_environmental_destroy_lifecycle",
):
    importlib.reload(importlib.import_module(name))
