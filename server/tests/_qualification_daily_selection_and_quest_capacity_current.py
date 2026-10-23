import importlib

for name in (
    "wakfu_server.quest_inventory",
    "wakfu_server.account_quest_inventory",
    "wakfu_server.items.quest_inventory",
    "wakfu_server.items.account_quest_inventory",
    "wakfu_server.achievements.rewards",
    "wakfu_server.objectives.environmental_recurring_storage",
    "test_recurring_daily_hunter_backend",
):
    importlib.reload(importlib.import_module(name))
