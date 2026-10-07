"""Stable world SDK entry; keep this path compatible with the existing bridge."""
if __package__:
    from .wakfu_ai.bridge.world_entry import run_npc_turn, native_exporter
else:
    from wakfu_ai.bridge.world_entry import run_npc_turn, native_exporter
