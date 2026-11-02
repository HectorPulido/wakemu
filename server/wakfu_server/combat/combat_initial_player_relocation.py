"""Validate ordinary fight placement away from prospective native spawn slots."""
from .combat_geometry import coordinate, prepare_geometry, reachable
from .combat_placement_footprints import covered_cells


def validated_destination(arena, *, original=None):
    record = arena.get("native_initial_player_relocation")
    pair = arena.get("participant_player_position")
    if (
        not isinstance(record, dict)
        or set(record) != {"schema", "physical_radius", "reserved_cells"}
        or record["schema"] != "wakemu-reserved-slot-placement-v1"
        or type(record["physical_radius"]) is not int
        or not 0 <= record["physical_radius"] <= 127
        or not isinstance(pair, (tuple, list))
        or len(pair) != 2
        or arena.get("native_encounter_scene_layout") is not None
    ):
        raise ValueError("Invalid reserved-slot player placement")
    source, destination = map(coordinate, pair)
    cells = frozenset(map(coordinate, arena["validated_cells"]))
    reserved = frozenset(map(coordinate, record["reserved_cells"]))
    if (
        source == destination
        or not reserved
        or not reserved <= cells
        or len(reserved) != len(record["reserved_cells"])
        or original is not None
        and source != tuple(original)
    ):
        raise ValueError(
            "Reserved-slot placement changed its world origin or native floor"
        )
    radius = record["physical_radius"]
    if (
        not covered_cells(source, radius, cells) & reserved
        or covered_cells(destination, radius, cells) & reserved
    ):
        raise ValueError("Reserved-slot placement does not clear its native footprint")
    from .combat_encounter_roles import roles_from_record

    roles = arena.get("native_encounter_roles")
    player_team = 0 if roles is None else roles_from_record(roles).player_team
    if destination not in set(map(coordinate, arena["placement_cells"][player_team])):
        raise ValueError("Reserved-slot player destination is outside placement")
    geometry = prepare_geometry(
        dict(map_id=arena["map_id"], cells=cells, edges=arena["valid_edges"])
    )
    if destination not in reachable(source, cells, geometry.outgoing):
        raise ValueError("Reserved-slot placement crosses disconnected native floors")
    scene = arena.get("native_encounter_scene")
    if scene is not None:
        from .combat_encounter_scene_policy import declared_spawn_cells
        from .combat_encounter_glyph_bootstrap import declared_environment_blockers

        descriptor = scene["descriptor"]
        expected = declared_spawn_cells(descriptor) | declared_environment_blockers(
            descriptor.get("native_initial_glyphs", ())
        )
        if reserved != expected:
            raise ValueError("Reserved-slot placement changed admitted scene slots")
    return destination
