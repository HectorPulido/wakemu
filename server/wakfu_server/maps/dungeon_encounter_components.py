"""Admission on a reviewed encounter's actual native physical component.

A mixed progression stage may include disconnected reading or transit areas.
Those areas remain traversable, but cannot receive a relocated monster fight.
Existing group receipts and the caller's selected roster remain authoritative.
"""


def require_component(
    topology, room, cells, player_position, member_positions, *, geometry=None
):
    """Return the existing native arena component or reject a foreign participant.

    Only explicitly component-bound rooms opt in. No coordinate, movement edge,
    actor position, resource, progression field or native interaction is changed.
    The same mutual-component/column selector is used by ordinary arena layout.
    """
    from wakfu_server.combat_geometry import (
        coordinate,
        encounter_component,
        prepare_geometry,
        published_geometry,
    )

    from wakfu_server.dungeon_encounter_regions import encounter_room

    room = encounter_room(room)
    marker = room.get("encounter_component")
    if marker is None:
        return cells
    if type(marker) is not int or marker < 0:
        raise ValueError("Dungeon encounter component evidence is invalid")
    native = prepare_geometry(
        published_geometry(topology["asset_map_id"]) if geometry is None else geometry
    )
    selected = frozenset(coordinate(cell) for cell in cells)
    anchor = coordinate(room["anchor"])
    if (
        native.map_id != topology["asset_map_id"]
        or not selected
        or not selected <= native.cells
        or anchor not in selected
    ):
        raise ValueError("Dungeon encounter component lacks its pinned native floor")
    members = tuple(coordinate(position) for position in member_positions)
    if not members:
        raise ValueError("Dungeon encounter component requires its selected group")
    section = prepare_geometry(
        dict(
            map_id=native.map_id,
            cells=selected,
            edges=tuple(
                (start, end)
                for start, end in native.edges
                if start in selected and end in selected
            ),
        )
    )
    component, _ = encounter_component(section, anchor)
    if any(
        position not in component
        for position in (coordinate(player_position), *members)
    ):
        raise ValueError(
            "Dungeon combat participant is outside its physical encounter component"
        )
    return frozenset(component)
