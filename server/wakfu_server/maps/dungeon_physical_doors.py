"""Frozen native walking gates controlled by committed private dungeon progress."""
import struct

POLICY = "native_physical_door_victory_policy"


def enabled(topology):
    return topology.get("policy") == POLICY


def _frontier(topology, unlocked_room):
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    if (
        type(unlocked_room) is not int
        or not 1 <= unlocked_room <= main_room_orders(topology)[-1]
    ):
        raise ValueError("Invalid physical dungeon progress frontier")
    return unlocked_room


def _opened(topology, door, unlocked_room, *, completed=False):
    """Keep native postboss entry paths and explicit completion gates distinct."""
    if door.get("requires_completion") is True:
        return completed and door["destination_room"] <= unlocked_room
    if door["destination_room"] <= unlocked_room:
        return True
    if completed and topology.get("entry_path_policy") is not None:
        from wakfu_server.dungeon_entry_paths import accessible_postboss_orders
        from wakfu_server.dungeon_optional_rooms import main_room_orders

        allowed = accessible_postboss_orders(dict(topology, _entry_main_completed=True))
        allowed = allowed | set(main_room_orders(topology))
        return door["source_room"] in allowed and door["destination_room"] in allowed
    return False


def blocked_cells(topology, unlocked_room, *, blocked_source_ids=(), completed=False):
    _frontier(topology, unlocked_room)
    if topology.get("_rotation_pending"):
        blocked_source_ids = set(blocked_source_ids) | {
            d["source_id"] for d in topology["physical_doors"]
        }
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    if type(completed) is not bool or (
        completed and unlocked_room != main_room_orders(topology)[-1]
    ):
        raise ValueError("Main completion differs from its terminal room frontier")
    from wakfu_server.combat_sn_path import NativeSnColumns
    from wakfu_server.dungeon_native_door_collision import native_blocking_cells

    # Canonical callers pass their existing run status. Preserve the136
    # projected postboss view for its older/private entry-path callsites.
    entry_completed = completed or (
        topology.get("entry_path_policy") is not None
        and topology.get("_entry_main_completed") is True
    )
    main_blocked = set()
    columns = None
    for door in topology["physical_doors"]:
        if (
            _opened(
                topology,
                door,
                unlocked_room,
                completed=(
                    completed
                    if door.get("requires_completion") is True
                    else entry_completed
                ),
            )
            and door.get("source_id") not in blocked_source_ids
        ):
            continue
        if columns is None:
            columns = NativeSnColumns.from_published(topology["asset_map_id"])
        main_blocked.update(
            native_blocking_cells(
                topology["asset_map_id"],
                door["position"],
                columns=columns,
                expected_source_sha256=columns.source_sha256,
            )
        )
    main_blocked = frozenset(main_blocked)
    from wakfu_server.dungeon_optional_vote_geometry import blocked_gate_cells
    from wakfu_server.dungeon_main_completion import blocked_cells as completion_blocked

    return (
        main_blocked
        | blocked_gate_cells(topology)
        | completion_blocked(topology, completed=completed)
    )


def packets(
    topology,
    *,
    map_id,
    instance_id,
    unlocked_room,
    completed=False,
    blocked_source_ids=()
):
    """Door native state 0 clears collision; state 1 closes it, independent of usable."""
    from wakfu_server.dungeon_object_states import physical_door_payload

    if (
        not enabled(topology)
        or topology["asset_map_id"] != map_id
        or type(instance_id) is not int
        or instance_id <= 0
    ):
        raise ValueError("Physical doors require their owned dungeon instance")
    _frontier(topology, unlocked_room)
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    if type(completed) is not bool or (
        completed and unlocked_room != main_room_orders(topology)[-1]
    ):
        raise ValueError("Invalid physical dungeon completion state")
    from wakfu_server.dungeon_main_completion import require_rule

    if any("requires_completion" in d for d in topology["physical_doors"]):
        require_rule(topology)
    output = []
    opened_sources = set()
    for door in topology["physical_doors"]:
        opened = (
            _opened(topology, door, unlocked_room, completed=completed)
            and door["source_id"] not in blocked_source_ids
        )
        if opened:
            opened_sources.add(door["source_id"])
        payload = physical_door_payload(opened=opened)
        output.append(
            (12344, struct.pack(">qH", door["source_id"], len(payload)) + payload)
        )
    for exit_object in topology.get("physical_exit_objects", ()):
        from wakfu_server.dungeon_object_states import state_packet
        from wakfu_server.generic_transports import source

        usable = exit_object["room_order"] == 1 or completed
        output.append(
            state_packet(
                source(map_id, exit_object["source_id"]),
                map_id=map_id,
                instance_id=instance_id,
                visible=usable,
                usable=usable,
            )
        )
    from wakfu_server.dungeon_optional_vote_geometry import gate_packets
    from wakfu_server import dungeon_gate_presentation

    return (
        tuple(output)
        + gate_packets(topology)
        + dungeon_gate_presentation.packets(topology, opened_source_ids=opened_sources)
    )


def validate_movement(
    topology, request, *, unlocked_room, blocked_source_ids=(), completed=False
):
    """Validate actual directed native exploration edges and locked gate cells.

    Called only for the pinned physical-door policy; no combat graph is changed.
    Native diagonal movement requires both cardinal alternatives to be valid.
    """
    if not enabled(topology):
        raise ValueError("Dungeon has no native physical walking policy")
    blocked = blocked_cells(
        topology,
        unlocked_room,
        blocked_source_ids=blocked_source_ids,
        completed=completed,
    )
    geometry = topology["exploration_geometry"]
    cells = set(map(tuple, geometry["cells"]))
    if topology.get("optional_vote_access") is not None:
        from wakfu_server.dungeon_optional_rooms import main_room_orders
        from wakfu_server.dungeon_optional_vote_geometry import extra_cells

        required = set(main_room_orders(topology))
        allowed = {
            tuple(c)
            for room in topology["rooms"]
            if room["order"] in required
            for c in room["cells"]
        }
        cells.intersection_update(allowed | set(extra_cells(topology)))
    edges = {(tuple(a), tuple(b)) for a, b in geometry["edges"]}
    current = tuple(request["start_position"][k] for k in ("x", "y", "z"))
    if current not in cells or current in blocked:
        raise ValueError("Dungeon movement starts outside unlocked native terrain")
    for step in request["steps"]:
        target = tuple(
            current[i] + step["d" + axis] for i, axis in enumerate(("x", "y", "z"))
        )
        if target not in cells or target in blocked:
            raise ValueError("Dungeon movement crosses a locked room gate")
        if abs(target[0] - current[0]) == 1 and abs(target[1] - current[1]) == 1:
            choices = []
            for x, y in ((target[0], current[1]), (current[0], target[1])):
                choices.append(
                    any(
                        (current, middle) in edges and (middle, target) in edges
                        for middle in cells
                        if middle[:2] == (x, y) and middle not in blocked
                    )
                )
            if not all(choices):
                raise ValueError("Dungeon diagonal bypasses native gate collision")
        elif (current, target) not in edges:
            raise ValueError("Dungeon movement leaves native exploration edges")
        current = target
    if current != tuple(request["end_position"][k] for k in ("x", "y", "z")):
        raise ValueError("Dungeon movement endpoint mismatch")
    return current
