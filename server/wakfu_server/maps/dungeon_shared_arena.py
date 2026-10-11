"""Opt-in sequential encounters sharing one proven native arena."""
POLICY = "native_shared_arena_sequential_policy"


def validate(topology):
    if topology.get("policy") != POLICY:
        return None
    rooms = topology.get("rooms", [])
    if (
        len(rooms) < 2
        or topology.get("doors")
        or topology.get("physical_doors")
        or topology.get("auto_edges")
        or topology.get("branch_routes")
    ):
        raise ValueError(
            "Shared arena requires sequential encounters without invented gates or branches"
        )
    evidence = topology.get("shared_arena_evidence")
    if (
        not isinstance(evidence, dict)
        or not evidence.get("source_url")
        or not evidence.get("authority")
    ):
        raise ValueError("Shared arena requires explicit reviewed sequence evidence")
    native = set(map(tuple, topology["exploration_geometry"]["cells"]))
    cells = None
    for order, room in enumerate(rooms, 1):
        owned = set(map(tuple, room["cells"]))
        if (
            room["order"] != order
            or not owned
            or len(owned) != len(room["cells"])
            or not owned.issubset(native)
            or tuple(room["anchor"]) not in owned
        ):
            raise ValueError(
                "Shared arena encounter has invalid native terrain or stage"
            )
        if cells is not None and cells != owned:
            raise ValueError(
                "Shared arena stages must own exactly identical native cells"
            )
        cells = owned
    exits = topology.get("physical_exit_objects", [])
    if (
        len(exits) != 1
        or exits[0]["room_order"] != 1
        or not exits[0].get("native_approach_cells")
        or not set(map(tuple, exits[0]["native_approach_cells"])).issubset(cells)
    ):
        raise ValueError(
            "Shared arena requires one reviewed native cancellation/completion exit"
        )
    return cells


def stage(topology, current_room):
    validate(topology)
    if type(current_room) is not int or not 1 <= current_room <= len(topology["rooms"]):
        raise ValueError("Shared arena requires authoritative current encounter stage")
    return current_room


def packets(topology, *, map_id, instance_id, unlocked_room, completed=False):
    from wakfu_server import dungeon_object_states, generic_transports

    stage(topology, unlocked_room)
    if (
        type(completed) is not bool
        or completed
        and unlocked_room != len(topology["rooms"])
    ):
        raise ValueError("Shared arena completion contradicts progression")
    if map_id != topology["asset_map_id"]:
        raise ValueError("Shared arena belongs to another asset map")
    source = generic_transports.source(
        map_id, topology["physical_exit_objects"][0]["source_id"]
    )
    if source is None:
        raise ValueError("Shared arena exit is absent from native catalog")
    return (
        dungeon_object_states.state_packet(
            source,
            map_id=map_id,
            instance_id=instance_id,
            visible=completed,
            usable=completed,
        ),
    )
