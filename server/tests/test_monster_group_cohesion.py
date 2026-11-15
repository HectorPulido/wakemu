"""Cohesion selection coverage now executes production Rust kernels.

mob_geometry::cohesion_contract maps the former cases to:
- compact_translation_keeps_offsets_and_missing_edge_never_becomes_a_native_step
- scattered_follower_uses_one_native_edge_toward_stationary_leader
- regrouping_cannot_increase_distance_or_teleport

Those cases retain offset/packet/immutability checks, native directed edges,
occupied and habitat rejection, empty-player inactivity, strict distance
improvement and no teleport. Missing compact edges reject rigid translation;
current flexible movement may advance members while preserving cohesion.
"""
