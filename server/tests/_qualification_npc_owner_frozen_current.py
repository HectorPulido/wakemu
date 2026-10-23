import importlib

for name in ("wakfu_server.maps.npc_world", "test_npc_world"):
    importlib.reload(importlib.import_module(name))
