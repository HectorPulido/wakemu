"""Synchronize in-memory planting occupations after durable ecology resets."""


def cancel_plantings(plantings, result):
    """Caller holds planting/group fences; cancel only the reset domain."""
    from .territory_cells import region_at

    scopes = result.get("scopes", ())
    cancelled = set(result.get("cancelled_characters", ()))
    for identity, ticket in tuple(plantings.pending.items()):
        prepared = ticket["prepared"]
        monster_resource = prepared["definition"]["monster_resource"]
        if monster_resource == bool(result.get("flora")):
            continue
        current, request = prepared["character"], prepared["request"]
        for map_id, instance_id, region_id in scopes:
            if (current["map_id"], current.get("instance_id", 0)) != (
                map_id,
                instance_id,
            ):
                continue
            if (
                region_id is None
                or region_at(map_id, request["x"], request["y"]) == region_id
            ):
                cancelled.add(identity)
                break
    for identity in cancelled:
        plantings.cancel(identity)
    return len(cancelled)
