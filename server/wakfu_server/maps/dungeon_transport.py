"""Configured native dungeon-entry transport with an atomic party transition.

Only configured native routes are intercepted. The caller must provide
authoritative implementations of both the native criterion and source
interaction checks; there is deliberately no default for IsNeoServer().
"""
from __future__ import annotations

import struct

from wakfu_server import dungeon_instances, generic_transports


_REQUEST = struct.Struct(">qiBi")


def resolve_request(entry_map_id, body):
    """Return a verified configured route/destination, or None for other links."""
    if type(entry_map_id) is not int or entry_map_id <= 0:
        raise ValueError("Invalid dungeon entry map")
    if (
        not isinstance(body, (bytes, bytearray, memoryview))
        or len(body) != _REQUEST.size
    ):
        raise ValueError("Invalid native teleporter request length")
    object_id, destination_id, flag, mode = _REQUEST.unpack(body)
    configured = dungeon_instances.route_for_entry(
        entry_map_id, object_id, destination_id
    )
    if configured is None:
        return None
    # cpJ12296: source long, destination int, flF.geE auto-downscale byte,
    # flF.GN selected Stasis int. Other transports keep their own guards.
    if flag not in (0, 1) or not 1 <= mode <= 10:
        raise ValueError("Unsupported native teleporter mode")

    source = generic_transports.source(entry_map_id, object_id)
    if source is None:
        raise ValueError("Configured dungeon source is missing from native catalog")
    destination = next(
        (
            row
            for row in source["destinations"]
            if row["destination_id"] == destination_id
        ),
        None,
    )
    if (
        destination is None
        or destination["criterion"] != configured.criterion
        or destination["cyZ"]
        != (
            configured.native_template_id
            if configured.native_template_id is not None
            else configured.template_id
        )
        or destination["map_id"] != configured.start_map_id
    ):
        raise ValueError("Configured dungeon route no longer matches native catalog")
    if destination.get("cyW", 0) > 0 and destination.get("item_reference", 0) > 0:
        raise ValueError("Dungeon entry requires an authoritative item transaction")
    if destination.get("cyX", 0) != 0:
        raise ValueError("Dungeon entry requires an authoritative kama transaction")
    if not destination["native_altitude_walkable"]:
        raise ValueError("Dungeon entry destination altitude is not verified walkable")
    return {
        "route": configured,
        "source": source,
        "difficulty_selection": None
        if (flag, mode) == (0, 2)
        else dict(stasis_level=mode, competitive=bool(flag)),
        "native_destination": destination,
        "destination": {
            "map_id": destination["map_id"],
            "x": destination["x"],
            "y": destination["y"],
            "z": destination["z"],
            "direction": destination["direction"],
        },
    }


def enter(
    store,
    account_id,
    generation,
    character_id,
    entry_map_id,
    body,
    *,
    criterion_allowed,
    source_allowed,
    initialize_instance=None,
    resolve_destination=None,
):
    """Authorize and atomically create/reuse a party run plus move its roster.

    `criterion_allowed(character, criterion)` must evaluate the exact native
    expression from trusted server configuration. `source_allowed(character,
    source)` must verify native approach/proximity. Both must return exactly
    True. Client bytes contain no live instance ID; the returned ID is minted
    by `dungeon_instances` and used for every member's location update.
    """
    resolved = resolve_request(entry_map_id, body)
    if resolved is None:
        return None
    if not callable(criterion_allowed):
        raise ValueError("Authoritative dungeon criterion evaluator required")
    if not callable(source_allowed):
        raise ValueError("Authoritative dungeon source check required")

    source = resolved["source"]
    route = resolved["route"]

    def authorize(character, selected_route):
        return (
            selected_route == route
            and source_allowed(character, dict(source)) is True
            and criterion_allowed(character, route.criterion) is True
        )

    difficulty_selection = resolved["difficulty_selection"]
    if difficulty_selection is None:
        from wakfu_server import dungeon_difficulty

        with store.connection() as db:
            try:
                native = dungeon_difficulty.definition(db, route.definition_id)
            except ValueError:
                native = None
        if native is not None and native.get("difficulty_available", False):
            difficulty_selection = dict(
                stasis_level=max(2, native["minimum_stasis"]), competitive=False
            )

    session = dungeon_instances.create_or_reuse(
        store,
        account_id,
        generation,
        character_id,
        route.key,
        authorize_entry=authorize,
        difficulty_selection=difficulty_selection,
        initialize_instance=initialize_instance,
        resolve_destination=resolve_destination,
        transition_destination={
            key: resolved["destination"][key] for key in ("map_id", "x", "y", "z")
        },
    )
    return {
        **session,
        "destination": {
            **resolved["destination"],
            **{key: session["transition"][key] for key in ("map_id", "x", "y", "z")},
            "instance_id": session["instance_id"],
        },
        "criterion": route.criterion,
        "template_id": route.template_id,
    }
