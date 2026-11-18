"""Emit mission events only for a committed, exact native transport endpoint.

The caller owns the position lease and movement transaction. Native source and
destination identities are checked again here so a map visit or administrative
teleport cannot stand in for using the reviewed entrance.
"""

from uuid import uuid4


def on_transition(db, store, source, saved, route):
    if "native_link_id" in route:
        return on_boat_transition(db, store, source, saved, route)
    identity = route.get("interactive_element_id")
    destination_id = route.get("destination_id")
    if (
        type(identity) is not int
        or type(destination_id) is not int
        or route.get("source_map") != source["map_id"]
        or source.get("instance_id", 0) != 0
        or saved.get("instance_id", 0) != 0
        or (source["id"], source["account_id"]) != (saved["id"], saved["account_id"])
    ):
        return []
    from wakfu_server import generic_transports

    native = generic_transports.source(source["map_id"], identity)
    if native is None:
        return []
    candidates = [
        target
        for target in native["destinations"]
        if target["destination_id"] == destination_id
    ]
    if len(candidates) != 1:
        return []
    target = candidates[0]
    if (
        target["cyZ"] >= 0
        or route.get("native_definition_id") != native["definition_id"]
        or any(
            saved.get(key) != target[key]
            or route.get("destination", {}).get(key) != target[key]
            for key in ("map_id", "x", "y", "z")
        )
    ):
        return []
    from . import mission_toolkit

    return mission_toolkit.settle(
        db,
        store,
        saved,
        token="native-transport-entry:" + uuid4().hex,
        kind="transport_entered",
        reference=destination_id,
    )


def on_boat_transition(db, store, source, saved, route):
    """Qualify a committed Boat route against its exact original endpoints."""
    from wakfu_server import native_boats

    if (
        source.get("instance_id", 0) != 0
        or saved.get("instance_id", 0) != 0
        or (source["id"], source["account_id"]) != (saved["id"], saved["account_id"])
    ):
        return []
    source_id, destination_id, link_id = (
        route.get(key) for key in ("source_id", "destination_id", "native_link_id")
    )
    if any(
        type(value) is not int or value <= 0
        for value in (source_id, destination_id, link_id)
    ):
        return []
    endpoints, indexed_links = native_boats._indexes()
    origin, destination = endpoints.get(source_id), endpoints.get(destination_id)
    links = indexed_links.get(frozenset((source_id, destination_id)), ())
    if (
        origin is None
        or destination is None
        or source_id == destination_id
        or origin["map_id"] != source["map_id"]
        or destination["map_id"] != saved["map_id"]
        or not any(link["id"] == link_id for link in links)
        or any(saved.get(key) != destination[key] for key in ("x", "y"))
        or any(
            saved.get(key) != route.get("destination", {}).get(key)
            for key in ("map_id", "instance_id", "x", "y", "z")
        )
    ):
        return []
    # Native Boat altitude is resolved by its existing geometry/arrival-column
    # authority before the fenced transition. Endpoint x/y and exact committed
    # route destination are checked here; a map visit has no Boat link proof.
    from . import mission_toolkit

    return mission_toolkit.settle(
        db,
        store,
        saved,
        token="native-boat-entry:" + uuid4().hex,
        kind="transport_entered",
        reference=destination_id,
    )
