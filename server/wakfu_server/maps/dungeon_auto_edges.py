"""Author and validate local room links against final destination anchors."""
from copy import deepcopy


LOCAL_POLICY = "local_accessible_anchor_policy"


def _rooms_and_pairs(topology):
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    rooms = topology["rooms"]
    if (
        not isinstance(rooms, list)
        or not rooms
        or any(not isinstance(room, dict) for room in rooms)
    ):
        raise ValueError("Automatic dungeon links require explicit rooms")
    orders = [room.get("order") for room in rooms]
    if any(type(order) is not int for order in orders) or orders != list(
        range(1, len(orders) + 1)
    ):
        raise ValueError("Automatic dungeon rooms require unique consecutive orders")
    main = main_room_orders(topology)
    return {room["order"]: room for room in rooms}, tuple(zip(main, main[1:]))


def _indexed_links(topology, pairs):
    links = topology.get("auto_edges", ())
    if not isinstance(links, (list, tuple)):
        raise ValueError("Automatic dungeon links must be an explicit sequence")
    indexed = {}
    for link in links:
        if not isinstance(link, dict):
            raise ValueError("Automatic dungeon link must be an object")
        pair = link.get("source_room"), link.get("destination_room")
        if (
            any(type(order) is not int for order in pair)
            or pair not in pairs
            or pair in indexed
        ):
            raise ValueError(
                "Automatic dungeon links must uniquely follow required rooms"
            )
        indexed[pair] = link
    return indexed


def validate_auto_edges(topology):
    """Reject inconsistent new publications without changing legacy pinned data.

    This belongs to configuration authoring/install, never pinned reads. Runtime
    recovery separately owns an existing malformed receipt or topology.
    """
    if topology.get("policy") != LOCAL_POLICY:
        if topology.get("auto_edges"):
            raise ValueError("Automatic room edges require an explicit local policy")
        return
    if topology.get("doors"):
        raise ValueError("Local automatic room links cannot claim native doors")
    rooms, pairs = _rooms_and_pairs(topology)
    indexed = _indexed_links(topology, pairs)
    if set(indexed) != set(pairs):
        raise ValueError("Automatic dungeon links omit a required room transition")
    for pair, link in indexed.items():
        destination = rooms[pair[1]]
        anchor = destination.get("anchor")
        selected = link.get("anchor")
        if (
            not isinstance(anchor, (list, tuple))
            or len(anchor) != 3
            or any(type(value) is not int for value in anchor)
            or not isinstance(selected, (list, tuple))
            or len(selected) != 3
            or any(type(value) is not int for value in selected)
            or tuple(selected) != tuple(anchor)
        ):
            raise ValueError(
                "Automatic dungeon link differs from its final room anchor"
            )
        if tuple(anchor) not in {tuple(cell) for cell in destination["cells"]}:
            raise ValueError(
                "Automatic dungeon room anchor is outside native room cells"
            )


def finalize_local_auto_edges(topology):
    """Explicitly author local links after all reviewed room anchors are final.

    Return a copy for a future configuration; do not rewrite immutable pins or
    reinterpret native physical/teleporter routes as automatic movement.
    """
    result = deepcopy(topology)
    if result.get("policy") != LOCAL_POLICY:
        validate_auto_edges(result)
        return result
    if result.get("doors"):
        raise ValueError("Local automatic room links cannot claim native doors")
    rooms, pairs = _rooms_and_pairs(result)
    indexed = _indexed_links(result, pairs)
    if indexed and set(indexed) != set(pairs):
        raise ValueError("Cannot author an incomplete automatic dungeon route")
    result["auto_edges"] = [
        dict(
            indexed.get(pair, {}),
            source_room=pair[0],
            destination_room=pair[1],
            anchor=deepcopy(rooms[pair[1]]["anchor"]),
        )
        for pair in pairs
    ]
    validate_auto_edges(result)
    return result
