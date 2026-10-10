"""Native manual dungeon traversal shared by physical gates and teleports."""
from wakfu_server import dungeon_physical_doors

TELEPORT_POLICY = "native_teleport_victory_policy"


def enabled(topology):
    return (
        dungeon_physical_doors.enabled(topology)
        or topology.get("policy") == TELEPORT_POLICY
    )


def object_room(topology, source):
    """Resolve literal source approaches without inventing walkable center cells."""
    asset_map = topology.get("asset_map_id")
    if asset_map is not None and source.get("map_id") != asset_map:
        raise ValueError("Native interactive object belongs to another asset map")
    cells = {tuple(c): r["order"] for r in topology["rooms"] for c in r["cells"]}
    center = tuple(source[k] for k in ("x", "y", "z"))
    center_room = cells.get(center)
    if topology.get("policy") != TELEPORT_POLICY:
        return center_room
    if asset_map is None:
        raise ValueError("Native teleport topology lacks an asset map")
    bindings = [b for b in topology.get("doors", ()) if b["source_id"] == source["id"]]
    bindings += [
        dict(b, source_room=b["room_order"])
        for b in topology.get("physical_exit_objects", ())
        if b["source_id"] == source["id"]
    ]
    if not bindings:
        return center_room
    rooms = {b["source_room"] for b in bindings}
    if len(rooms) != 1:
        raise ValueError("Native interactive object has ambiguous room bindings")
    room = next(iter(rooms))
    literal = {
        tuple(p[k] for k in ("x", "y", "z"))
        for p in source.get("approach_positions", ())
    }
    if source.get("approach_blocks_center") is False:
        literal.add(center)
    for binding in bindings:
        approaches = set(map(tuple, binding.get("native_approach_cells", ())))
        if (
            not approaches
            or not approaches.issubset(literal)
            or any(cells.get(p) != room for p in approaches)
        ):
            raise ValueError(
                "Native interactive room lacks verified literal approaches"
            )
        if (
            binding.get("source_position") is not None
            and tuple(binding["source_position"]) != center
        ):
            raise ValueError("Native interactive source position changed")
    if center_room is not None and center_room != room:
        raise ValueError("Native source center contradicts its approach room")
    return room


def packets(topology, *, map_id, instance_id, unlocked_room, completed=False):
    if dungeon_physical_doors.enabled(topology):
        return dungeon_physical_doors.packets(
            topology,
            map_id=map_id,
            instance_id=instance_id,
            unlocked_room=unlocked_room,
            completed=completed,
        )
    if topology.get("policy") != TELEPORT_POLICY:
        raise ValueError("Dungeon has no supported native manual flow")
    from wakfu_server import dungeon_object_states, generic_transports

    return dungeon_object_states.packets(
        topology,
        [s for s in generic_transports._CATALOG if s["map_id"] == map_id],
        map_id=map_id,
        instance_id=instance_id,
        unlocked_room=unlocked_room,
        completed=completed,
    )


def validate_movement(topology, request, *, unlocked_room):
    if not enabled(topology):
        raise ValueError("Dungeon has no supported native exploration policy")
    if topology.get("policy") == TELEPORT_POLICY:
        current = tuple(request["start_position"][k] for k in ("x", "y", "z"))
        cells = {tuple(c): r["order"] for r in topology["rooms"] for c in r["cells"]}
        visited = [current]
        for step in request["steps"]:
            current = tuple(
                current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
            )
            visited.append(current)
        if any(cells.get(p, unlocked_room + 1) > unlocked_room for p in visited):
            raise ValueError("Native exploration crosses a locked room")
    # Reuse the proven native edge validator; never alter combat geometry.
    return dungeon_physical_doors.validate_movement(
        dict(topology, policy=dungeon_physical_doors.POLICY),
        request,
        unlocked_room=unlocked_room,
    )
