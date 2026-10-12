"""Explicit native indexed-surface authority for fresh summon registration."""


def native_summon_placement(fight, actor):
    """Keep legacy movement cells; qualify other cells through actual QI.X/QK."""
    if actor.position in fight.walkable:
        return True
    position = actor.position
    if (
        not isinstance(position, tuple)
        or len(position) != 3
        or any(type(value) is not int for value in position)
        or not -32768 <= position[2] <= 32767
    ):
        return False
    provenance = getattr(fight, "native_qi_surface_provenance", None)
    arena = getattr(fight, "native_qi_snapshot", None)
    if (
        not isinstance(provenance, dict)
        or not isinstance(arena, dict)
        or getattr(fight, "native_qi_slots", None) is None
    ):
        return False
    from .combat_qi_surface_catalog import (
        native_qi_surface_provenance,
        native_qi_surfaces,
    )
    from .combat_qi_snapshot import NativeQISnapshot
    from .combat_cell_group import selected_height
    from .combat_summon import fresh_summon_slot_owned

    map_id = provenance.get("map_id")
    if provenance != native_qi_surface_provenance(map_id):
        raise ValueError("Summon selected-surface provenance mismatch")
    qi = NativeQISnapshot(arena)
    x, y, z = position
    if not qi.aK(x, y):
        return False
    # QI.f registers an owned QK using rectangle membership, not movement
    # masks. QI.X supplies its exact indexed Vy height, independently of LOS.
    if selected_height(qi, native_qi_surfaces(map_id), x, y) != z:
        return False
    return fresh_summon_slot_owned(fight, actor)
