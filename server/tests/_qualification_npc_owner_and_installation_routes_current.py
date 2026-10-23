import importlib

for name in (
    "wakfu_server.maps.npc_world",
    "test_npc_observed_dialogue",
    "test_npc_protectors",
    "test_export_installation_seed",
):
    importlib.reload(importlib.import_module(name))
