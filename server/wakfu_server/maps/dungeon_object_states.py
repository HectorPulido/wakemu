"""Native dungeon teleporter visibility/usability from committed room progress.

Official 12344 vectors reveal a door, then enable it without changing its
approach mask. The partial fj field 2 state is compatible with both clients.
This module encodes state only; the caller authorizes the owned private run.
"""
import struct


def _integer(value, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid native dungeon state integer")
    return value


def state_payload(*, visible, usable, state_id=1):
    """Encode the verified bEI/bEG field 2 with neutral auxiliary flags."""
    if type(visible) is not bool or type(usable) is not bool:
        raise ValueError("Native visibility and usability must be booleans")
    if usable and not visible:
        raise ValueError("A usable dungeon door must be visible")
    _integer(state_id, 0, 32767)
    # fj partial field header followed by state, visible, usable, four flags,
    # and an empty additional-action collection, as read by bEI/bEG field 2.
    return bytes.fromhex("01020000000602") + struct.pack(
        ">h6Bi", state_id, visible, usable, 0, 0, 0, 0, 0
    )


def state_packet(source, *, map_id, instance_id, visible, usable, state_id=1):
    """Encode only a registered native Teleporter owned by this asset map."""
    from wakfu_server.generic_transports import source as native_source

    _integer(instance_id, 1, 9223372036854775807)
    _integer(map_id, 0, 32767)
    identity = _integer(source.get("id"), 1, 9223372036854775807)
    _integer(source.get("map_id"), 0, 32767)
    if source.get("map_id") != map_id or native_source(map_id, identity) is None:
        raise ValueError("Dungeon state object is outside the native asset map")
    payload = state_payload(visible=visible, usable=usable, state_id=state_id)
    return 12344, struct.pack(">qH", identity, len(payload)) + payload


def native_interactions_enabled(topology):
    """Local automatic progression does not authorize native teleport actions.

    The dispatcher must enforce this alongside visibility updates; packet state
    alone is not server-side transport authorization.
    """
    return topology.get("policy") != "local_accessible_anchor_policy"


def packets(topology, sources, *, map_id, instance_id, unlocked_room, completed=False):
    """Hydrate all reviewed routes, including reverse routes and exterior exits.

    unlocked_room is the committed progression frontier, not the member's
    current physical room. An exterior exit in room 1 stays available; a final
    room exit becomes available after the final victory. Other exterior exits
    are unsupported rather than silently opened.
    """
    if type(completed) is not bool:
        raise ValueError("Invalid dungeon completion state")
    if topology.get("asset_map_id", map_id) != map_id:
        raise ValueError("Dungeon topology belongs to another native asset")
    rooms = tuple(topology["rooms"])
    count = len(rooms)
    _integer(unlocked_room, 1, count)
    if completed and unlocked_room != count:
        raise ValueError("Completed dungeon has an inconsistent room frontier")
    cells = {}
    for expected, room in enumerate(rooms, 1):
        if type(room["order"]) is not int or room["order"] != expected:
            raise ValueError("Dungeon room order is not contiguous")
        for cell in room["cells"]:
            key = tuple(cell)
            if key in cells:
                raise ValueError("Dungeon terrain belongs to multiple rooms")
            cells[key] = expected
    owned = {}
    for source in sources:
        if source["map_id"] != map_id or source["id"] in owned:
            raise ValueError("Conflicting dungeon native object ownership")
        owned[source["id"]] = source
    if not native_interactions_enabled(topology):
        if topology["doors"]:
            raise ValueError(
                "Automatic dungeon topology cannot claim reviewed native doors"
            )
        # Native objects belong to the asset, not the generated logical rooms.
        # Their exterior/internal destinations are deliberately not interpreted
        # as local progression or exits. Automatic movement owns both paths.
        return tuple(
            state_packet(
                owned[identity],
                map_id=map_id,
                instance_id=instance_id,
                visible=False,
                usable=False,
            )
            for identity in sorted(owned)
        )
    availability = {}
    for door in topology["doors"]:
        source = owned.get(door["source_id"])
        if source is None:
            raise ValueError("Dungeon door has no owned native object")
        start, end = door["source_room"], door["destination_room"]
        _integer(start, 1, count)
        _integer(end, 1, count)
        if abs(start - end) != 1:
            raise ValueError("Dungeon door does not connect adjacent reviewed rooms")
        position = tuple(source[axis] for axis in ("x", "y", "z"))
        if cells.get(position) != start:
            raise ValueError("Dungeon door source disagrees with native terrain")
        destination = next(
            (
                row
                for row in source["destinations"]
                if row["destination_id"] == door["destination_id"]
            ),
            None,
        )
        if destination is None or destination["map_id"] != map_id:
            raise ValueError("Dungeon door route is not native")
        target = tuple(destination[axis] for axis in ("x", "y", "z"))
        if cells.get(target) != end:
            raise ValueError("Dungeon door destination disagrees with native terrain")
        enabled = max(start, end) <= unlocked_room
        if source["id"] in availability and availability[source["id"]] != enabled:
            raise ValueError("Native object has conflicting door states")
        availability[source["id"]] = enabled
    for source in owned.values():
        # The reviewed internal topology already selected its allowed route.
        # A native object may also advertise a mutually exclusive Neo-server
        # destination; it does not turn this door into an exterior exit.
        if source["id"] in availability:
            continue
        exterior = [
            row
            for row in source["destinations"]
            if row["map_id"] != map_id and not row.get("criterion", "").strip()
        ]
        if not exterior:
            continue
        order = cells.get(tuple(source[axis] for axis in ("x", "y", "z")))
        if order not in (1, count):
            raise ValueError("Unsupported exterior exit in an intermediate room")
        availability[source["id"]] = order == 1 or completed
    return tuple(
        state_packet(
            owned[identity],
            map_id=map_id,
            instance_id=instance_id,
            visible=enabled,
            usable=enabled,
        )
        for identity, enabled in sorted(availability.items())
    )


def transition_packets(
    topology,
    sources,
    *,
    map_id,
    instance_id,
    previous_unlocked_room,
    unlocked_room,
    previous_completed=False,
    completed=False
):
    """Reveal newly unlocked native objects before enabling their actions.

    Reconnect hydration uses packets(); a committed victory uses this delta.
    Repeated receipt delivery produces no extra state changes when the caller
    supplies identical before/after progression state.
    """
    sources = tuple(sources)
    before = packets(
        topology,
        sources,
        map_id=map_id,
        instance_id=instance_id,
        unlocked_room=previous_unlocked_room,
        completed=previous_completed,
    )
    after = packets(
        topology,
        sources,
        map_id=map_id,
        instance_id=instance_id,
        unlocked_room=unlocked_room,
        completed=completed,
    )
    if unlocked_room < previous_unlocked_room or previous_completed and not completed:
        raise ValueError("Dungeon object state progression cannot move backward")
    old = {struct.unpack_from(">q", body)[0]: body for opcode, body in before}
    owned = {source["id"]: source for source in sources}
    result = []
    for opcode, body in after:
        identity = struct.unpack_from(">q", body)[0]
        if old.get(identity) == body:
            continue
        # Offsets 19/20 are visible/usable in the verified 12344 fixed vector.
        if not old[identity][19] and body[19] and body[20]:
            result.append(
                state_packet(
                    owned[identity],
                    map_id=map_id,
                    instance_id=instance_id,
                    visible=True,
                    usable=False,
                )
            )
        result.append((opcode, body))
    return tuple(result)
