import importlib

for name in (
    "wakfu_server.achievements.storage",
    "wakfu_server.achievements.rewards",
    "wakfu_server.achievements.service",
    "test_achievement_reward_extensions_postgres",
):
    importlib.reload(importlib.import_module(name))
