"""Server-owned native activation projection for reviewed seasonal entrances.

Original bBH custom actions avoid obsolete client-side flE gates. Admission
still executes the exact configured native transport and its ordinary guards.
"""
import struct

PROTOTYPE_ID = 19825  # Original aLM: blank GenericActivableInteractiveElement39.
_REVIEWED = frozenset(((527, 20179, 443), (472, 17452, 476)))
_ENTRY_MAPS = frozenset(source_map for source_map, _, _ in _REVIEWED)


def binding(map_id, source_id):
    from wakfu_server import (
        generic_transports,
        dungeon_instances,
        exploration_transport,
        travel_mists,
    )

    mist = travel_mists.binding(map_id, source_id)
    if mist is not None:
        return mist
    artifact = exploration_transport.binding(map_id, source_id)
    if artifact is not None:
        return artifact

    if map_id not in _ENTRY_MAPS:
        return None
    source = generic_transports.source(map_id, source_id)
    if source is None:
        return None
    candidates = []
    for destination in source["destinations"]:
        if (map_id, source_id, destination["map_id"]) not in _REVIEWED:
            continue
        route = dungeon_instances.route_for_entry(
            map_id, source_id, destination["destination_id"]
        )
        if route is not None:
            from wakfu_server.maps.dungeon_transport import resolve_request

            request = struct.pack(
                ">qiBi", source_id, destination["destination_id"], 0, 2
            )
            resolved = resolve_request(map_id, request)
            if (
                resolved is None
                or resolved["route"].start_map_id != destination["map_id"]
            ):
                continue
            route_key = route.key
        else:
            continue
        candidates.append(
            dict(source=source, destination=destination, route_key=route_key)
        )
    if len(candidates) > 1:
        raise ValueError("Ambiguous reviewed seasonal gateway")
    return candidates[0] if candidates else None


def _parts(blob):
    if not blob or len(blob) < 1 + 5 * blob[0]:
        raise ValueError("Invalid native gateway parts")
    header = 1 + 5 * blob[0]
    entries = [
        struct.unpack_from(">BI", blob, 1 + 5 * index) for index in range(blob[0])
    ]
    if (
        len({part for part, _ in entries}) != len(entries)
        or len({offset for _, offset in entries}) != len(entries)
        or any(not header <= offset < len(blob) for _, offset in entries)
    ):
        raise ValueError("Invalid native gateway part offsets")
    ordered = sorted(entries, key=lambda entry: entry[1])
    return {
        part: blob[
            offset : ordered[index + 1][1] if index + 1 < len(ordered) else len(blob)
        ]
        for index, (part, offset) in enumerate(ordered)
    }


def _encode_parts(parts):
    header = bytearray((len(parts),))
    payload = bytearray()
    offset = 1 + 5 * len(parts)
    for part, data in sorted(parts.items()):
        header.extend(struct.pack(">BI", part, offset + len(payload)))
        payload.extend(data)
    return bytes(header + payload)


def appearance(row, current_binding):
    """Retain the original native geometry and replace only its interaction."""
    from wakfu_server import world_static

    source = current_binding["source"]
    if (
        row["type"] != source.get("native_type", "Teleporter")
        or row["id"] != source["id"]
        or row["map_id"] != source["map_id"]
        or any(row[axis] != source[axis] for axis in ("x", "y", "z"))
    ):
        raise ValueError("Seasonal gateway native object identity changed")
    parts = _parts(bytes.fromhex(row["payload_hex"]))
    if set(parts) != {0, 1} or not parts[1] or parts[1][0] != 1:
        raise ValueError("Unqualified native seasonal geometry layout")
    native = source["native_parameters"].encode("utf-8")
    marker = struct.pack(">H", len(native)) + native
    if parts[1].count(marker) != 1:
        raise ValueError("Native seasonal parameter binding changed")
    parameters = current_binding.get("activation_parameters", b"{1;desc.mru.entrer}")
    parts[1] = parts[1].replace(marker, struct.pack(">H", len(parameters)) + parameters)
    state = _parts(world_static._DUNGEON_ENTRY_STATE)
    if set(state) != {2}:
        raise ValueError("Unqualified native seasonal activation state")
    return _encode_parts({**parts, **state})


def projected_attachment(row, current):
    """Encode an explicitly bound original activation with unchanged geometry."""
    blob = appearance(row, current)
    coordinates = tuple(row[key] for key in ("x", "y", "z"))
    if any(
        type(value) not in (int, float) or value != int(value) for value in coordinates
    ):
        raise ValueError("Native seasonal gateway position is not integral")
    x, y, z = map(int, coordinates)
    if not (-131071 <= x <= 131072 and -131071 <= y <= 131072 and -511 <= z <= 512):
        raise ValueError("Native seasonal gateway position exceeds packed bounds")
    packed = ((x + 131071) << 28) | ((y + 131071) << 10) | (z + 511)
    return 13664, (
        struct.pack(">hqqH", 1, row["id"], PROTOTYPE_ID, len(blob))
        + blob
        + struct.pack(">q", packed)
    )


def attachment(row, scope):
    """Replace the first native attachment, keeping the original scene UID."""
    if scope.get("instance_id", 0) != 0:
        return None
    from wakfu_server import exploration_artifact_actions

    artifact = exploration_artifact_actions.attachment(row, scope)
    if artifact is not None:
        return artifact
    current = binding(scope.get("map_id"), row["id"])
    return None if current is None else projected_attachment(row, current)


def activation(character, body):
    """Translate only the qualified owned native ACTIVATE request's route."""
    if not isinstance(body, bytes) or len(body) != 12:
        return None
    source_id, action, padding = struct.unpack(">qHH", body)
    current = binding(character["map_id"], source_id)
    if current is None:
        return None
    if character.get("instance_id", 0) != 0 or padding != 0:
        raise ValueError("Invalid native seasonal gateway activation")
    if current["route_key"] in ("travel_mist", "exploration_artifact"):
        from wakfu_server import exploration_transport

        destination, request = exploration_transport.request(current, action)
    else:
        if action != 0:
            raise ValueError("Invalid native seasonal gateway activation")
        destination = current["destination"]
        request = struct.pack(">qiBi", source_id, destination["destination_id"], 0, 2)
    return dict(
        route_key=current["route_key"],
        source_id=source_id,
        destination_map_id=destination["map_id"],
        body=request,
    )
