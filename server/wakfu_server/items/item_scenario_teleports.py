"""Original bIn server-side travel scenarios with durable destination authority."""
import hashlib
import json

ACTIONS = {
    7137: dict(
        item_ref=19022,
        action_id=7137,
        native_class="bIn",
        criteria="",
        parameters=["1855"],
    ),
    10859: dict(
        item_ref=19020,
        action_id=10859,
        native_class="bIn",
        criteria="",
        parameters=["2368"],
    ),
}
# Original nation.short IDs and content.77 map labels prove this correspondence.
# The exact original server arrival coordinate is absent from scenario2368;
# Wakemu deliberately arrives beside the nation's real native RespawnPoint.
NATION_MAPS = {30: 1134, 31: 1136, 32: 1137, 33: 1135}
SOURCE_SHA256 = hashlib.sha256(
    json.dumps(
        dict(actions=ACTIONS, nation_maps=NATION_MAPS),
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
).hexdigest()


def action_class(body):
    import struct

    if not isinstance(body, bytes) or len(body) < 4:
        return None
    identity = struct.unpack_from(">i", body)[0]
    if identity not in ACTIONS:
        return None
    if len(body) != 12:
        raise ValueError("Invalid native scenario teleport request")
    return "bIn"


def plan(action_id, character):
    from wakfu_server.phoenix_points import destination, saved_identity, points

    if character.get("health_dead", False) or character.get("hp", 1) <= 0:
        raise ValueError(
            "No puedes utilizar este objeto mientras estás fuera de combate"
        )
    row = ACTIONS.get(action_id)
    if row is None:
        raise ValueError("Unknown native travel scenario")
    if action_id == 10859:
        from wakfu_server.nation_state import nation_id
        from wakfu_server.phoenix_points import point_destination

        map_id = NATION_MAPS.get(nation_id(character))
        candidates = [point for point in points().values() if point["map_id"] == map_id]
        if len(candidates) != 1:
            raise ValueError(
                "Debes pertenecer a una nación con un destino de regreso disponible"
            )
        point = candidates[0]
        chosen = point_destination(point["id"])
    else:
        chosen = destination(character)
        point = points()[saved_identity(character)]
    return dict(
        row,
        destination=chosen,
        requested_destination=dict(
            map_id=point["map_id"],
            x=int(point["x"]),
            y=int(point["y"]),
            z=int(point["z"]),
        ),
        arrival_policy=(
            "wakemu_native_nation_phoenix_neighbor"
            if action_id == 10859
            else "native_walkable_neighbor_of_bound_respawn_point"
        ),
        recall_policy=(
            "native_scenario2368_nation"
            if action_id == 10859
            else "native_scenario1855_saved_phoenix"
        ),
        source_sha256=SOURCE_SHA256,
    )
