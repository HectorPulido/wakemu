"""Frozen native walking gates controlled by committed private dungeon progress."""
import struct

POLICY = "native_physical_door_victory_policy"


def enabled(topology):
    return topology.get("policy") == POLICY


def _frontier(topology, unlocked_room):
    if type(unlocked_room) is not int or not 1 <= unlocked_room <= len(
        topology["rooms"]
    ):
        raise ValueError("Invalid physical dungeon progress frontier")
    return unlocked_room


def blocked_cells(topology, unlocked_room):
    _frontier(topology, unlocked_room)
    return frozenset(
        tuple(d["position"])
        for d in topology["physical_doors"]
        if d["destination_room"] > unlocked_room
    )


def packets(topology, *, map_id, instance_id, unlocked_room, completed=False):
    """Door native state 0 clears collision; state 1 closes it, independent of usable."""
    from wakfu_server.dungeon_object_states import state_payload

    if (
        not enabled(topology)
        or topology["asset_map_id"] != map_id
        or type(instance_id) is not int
        or instance_id <= 0
    ):
        raise ValueError("Physical doors require their owned dungeon instance")
    _frontier(topology, unlocked_room)
    if type(completed) is not bool or (
        completed and unlocked_room != len(topology["rooms"])
    ):
        raise ValueError("Invalid physical dungeon completion state")
    output = []
    for door in topology["physical_doors"]:
        opened = door["destination_room"] <= unlocked_room
        # Native Door state alone can leave a closed sprite on loaded views.
        # Hide opened gates through the native view visibility update.
        payload = state_payload(
            visible=not opened, usable=False, state_id=0 if opened else 1
        )
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
    return tuple(output)


def validate_movement(topology, request, *, unlocked_room):
    """Validate actual directed native exploration edges and locked gate cells.

    Called only for the pinned physical-door policy; no combat graph is changed.
    Native diagonal movement requires both cardinal alternatives to be valid.
    """
    if not enabled(topology):
        raise ValueError("Dungeon has no native physical walking policy")
    blocked = blocked_cells(topology, unlocked_room)
    geometry = topology["exploration_geometry"]
    cells = set(map(tuple, geometry["cells"]))
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
