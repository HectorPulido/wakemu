"""Native manual dungeon traversal shared by physical gates and teleports."""
from wakfu_server import dungeon_physical_doors

TELEPORT_POLICY = "native_teleport_victory_policy"
MIXED_POLICY = "native_mixed_victory_policy"


def validate_transport_binding(topology, binding):
    """Validate an explicit transport frontier, including reviewed hub returns.

    Nonadjacent travel is opt-in for mixed native flows. Its gate identifies
    the victory that first unlocks the higher endpoint, never the source room.
    Literal source/destination verification remains the caller's responsibility.
    """
    start, end = binding["source_room"], binding["destination_room"]
    orders = {room["order"] for room in topology["rooms"]}
    if (
        type(start) is not int
        or type(end) is not int
        or start not in orders
        or end not in orders
    ):
        raise ValueError("Native transport endpoints leave reviewed rooms")
    mixed = topology.get("policy") == MIXED_POLICY
    gate = binding.get("progression_gate_room")
    if "progression_gate_room" in binding and (
        not mixed
        or type(gate) is not int
        or start == end
        or gate != max(start, end) - 1
    ):
        raise ValueError("Native transport progression gate contradicts its endpoints")
    if start == end:
        if not mixed:
            raise ValueError(
                "Same-stage native transport requires a reviewed mixed flow"
            )
        return None
    if abs(start - end) > 1 and (not mixed or gate is None):
        raise ValueError(
            "Nonadjacent native transport requires an explicit progression gate"
        )
    return max(start, end) - 1


def disabled_source_ids(topology, sources):
    """Validate explicit local exclusions without hiding a reviewed main path."""
    records = topology.get("disabled_native_sources", ())
    if not records:
        return frozenset()
    if topology.get("policy") != MIXED_POLICY or not isinstance(records, list):
        raise ValueError("Native source exclusions require an explicit mixed policy")
    from wakfu_server.dungeon_runtime_config import canonical_hash

    owned = {s["id"]: s for s in sources if s["map_id"] == topology["asset_map_id"]}
    mandatory = {
        b["source_id"]
        for key in ("doors", "physical_doors", "physical_exit_objects")
        for b in topology.get(key, ())
    }
    disabled = set()
    for record in records:
        if not isinstance(record, dict) or set(record) != {
            "source_id",
            "reason",
            "source_sha256",
        }:
            raise ValueError(
                "Native source exclusion lacks exact identity, reason and hash"
            )
        identity = record["source_id"]
        if (
            type(identity) is not int
            or identity <= 0
            or identity in disabled
            or identity in mandatory
            or identity not in owned
            or not isinstance(record["reason"], str)
            or not record["reason"].strip()
            or record["source_sha256"] != canonical_hash(owned[identity])
        ):
            raise ValueError(
                "Native source exclusion conflicts with its catalog or reviewed main path"
            )
        disabled.add(identity)
    return frozenset(disabled)


def enabled(topology):
    return (
        dungeon_physical_doors.enabled(topology)
        or topology.get("policy") == "native_shared_arena_sequential_policy"
        or topology.get("policy") in (TELEPORT_POLICY, MIXED_POLICY)
    )


def object_room(topology, source):
    """Resolve literal source approaches without inventing walkable center cells."""
    if topology.get("policy") == "native_shared_arena_sequential_policy":
        from wakfu_server import dungeon_shared_arena

        cells = dungeon_shared_arena.validate(topology)
        if source.get("map_id") != topology["asset_map_id"]:
            raise ValueError("Shared arena source belongs to another asset map")
        exits = topology["physical_exit_objects"]
        return 1 if source["id"] == exits[0]["source_id"] else None
    asset_map = topology.get("asset_map_id")
    if asset_map is not None and source.get("map_id") != asset_map:
        raise ValueError("Native interactive object belongs to another asset map")
    cells = {tuple(c): r["order"] for r in topology["rooms"] for c in r["cells"]}
    center = tuple(source[k] for k in ("x", "y", "z"))
    center_room = cells.get(center)
    if topology.get("policy") not in (TELEPORT_POLICY, MIXED_POLICY):
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
    if topology.get("policy") == "native_shared_arena_sequential_policy":
        from wakfu_server import dungeon_shared_arena

        return dungeon_shared_arena.packets(
            topology,
            map_id=map_id,
            instance_id=instance_id,
            unlocked_room=unlocked_room,
            completed=completed,
        )
    if dungeon_physical_doors.enabled(topology):
        return dungeon_physical_doors.packets(
            topology,
            map_id=map_id,
            instance_id=instance_id,
            unlocked_room=unlocked_room,
            completed=completed,
        )
    if topology.get("policy") not in (TELEPORT_POLICY, MIXED_POLICY):
        raise ValueError("Dungeon has no supported native manual flow")
    from wakfu_server import dungeon_object_states, generic_transports

    transport_packets = dungeon_object_states.packets(
        topology,
        [s for s in generic_transports._CATALOG if s["map_id"] == map_id],
        map_id=map_id,
        instance_id=instance_id,
        unlocked_room=unlocked_room,
        completed=completed,
    )
    if topology.get("policy") != MIXED_POLICY:
        return transport_packets
    import struct

    gate_ids = {d["source_id"] for d in topology["physical_doors"]}
    from wakfu_server import dungeon_branches

    gate_packets = dungeon_physical_doors.packets(
        dict(topology, policy=dungeon_physical_doors.POLICY),
        map_id=map_id,
        instance_id=instance_id,
        unlocked_room=unlocked_room,
        completed=completed,
        blocked_source_ids=dungeon_branches.unselected_gate_ids(topology),
    )
    return transport_packets + tuple(
        packet
        for packet in gate_packets
        if struct.unpack_from(">q", packet[1])[0] in gate_ids
    )


def validate_movement(topology, request, *, unlocked_room):
    if topology.get("policy") == "native_shared_arena_sequential_policy":
        from wakfu_server import dungeon_shared_arena

        cells = dungeon_shared_arena.validate(topology)
        dungeon_shared_arena.stage(topology, unlocked_room)
        current = tuple(request["start_position"][k] for k in ("x", "y", "z"))
        if current not in cells:
            raise ValueError("Shared arena movement starts outside reviewed cells")
        for step in request["steps"]:
            current = tuple(
                current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
            )
            if current not in cells:
                raise ValueError("Shared arena movement leaves reviewed cells")
    if not enabled(topology):
        raise ValueError("Dungeon has no supported native exploration policy")
    if topology.get("policy") in (TELEPORT_POLICY, MIXED_POLICY):
        current = tuple(request["start_position"][k] for k in ("x", "y", "z"))
        cells = {tuple(c): r["order"] for r in topology["rooms"] for c in r["cells"]}
        if topology.get("policy") == MIXED_POLICY:
            cells.update(
                {
                    tuple(g["position"]): g["destination_room"]
                    for g in topology["physical_doors"]
                }
            )
            from wakfu_server import dungeon_branches

            allowed = dungeon_branches.allowed_cells(topology)
            if allowed is not None:
                cells = {
                    position: room
                    for position, room in cells.items()
                    if position in allowed
                }
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
        blocked_source_ids=(
            dungeon_branches.unselected_gate_ids(topology)
            if topology.get("policy") == MIXED_POLICY
            else ()
        ),
    )


def exit_available(topology, binding, *, completed):
    """Shared arena native exit opens only after the final encounter."""
    if binding is None:
        return False
    if topology.get("policy") == "native_shared_arena_sequential_policy":
        from wakfu_server import dungeon_shared_arena

        dungeon_shared_arena.validate(topology)
        return completed is True
    return binding["room_order"] == 1 or completed is True
