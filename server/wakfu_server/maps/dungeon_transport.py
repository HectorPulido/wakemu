"""Configured native dungeon-entry transport with an atomic party transition.

Only configured native routes are intercepted. The caller must provide
authoritative implementations of both the native criterion and source
interaction checks; there is deliberately no default for IsNeoServer().
"""

from __future__ import annotations

from contextlib import nullcontext

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
    return resolve_route(entry_map_id, object_id, destination_id, flag=flag, mode=mode)


def resolve_route(entry_map_id, object_id, destination_id, *, flag=0, mode=2):
    """Resolve an actual native route from source-bound server interaction facts."""
    if (
        any(
            type(value) is not int
            for value in (entry_map_id, object_id, destination_id, flag, mode)
        )
        or entry_map_id <= 0
    ):
        raise ValueError("Invalid native route identity")
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
    if destination.get("cyX", 0) != 0:
        raise ValueError("Dungeon entry requires an authoritative kama transaction")
    if not destination["native_altitude_walkable"]:
        raise ValueError("Dungeon entry destination altitude is not verified walkable")
    return {
        "route": configured,
        "source": source,
        "difficulty_selection": (
            None
            if (flag, mode) == (0, 2)
            else dict(stasis_level=mode, competitive=bool(flag))
        ),
        "native_destination": destination,
        "destination": {
            "map_id": destination["map_id"],
            "x": destination["x"],
            "y": destination["y"],
            "z": destination["z"],
            "direction": destination["direction"],
        },
    }


def _enter(
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
    allowed_position_accounts=None,
    _db=None,
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
    return enter_resolved(
        store,
        account_id,
        generation,
        character_id,
        resolved,
        criterion_allowed=criterion_allowed,
        source_allowed=source_allowed,
        initialize_instance=initialize_instance,
        resolve_destination=resolve_destination,
        allowed_position_accounts=allowed_position_accounts,
        _db=_db,
    )


def enter_resolved(
    store,
    account_id,
    generation,
    character_id,
    resolved,
    *,
    criterion_allowed,
    source_allowed,
    initialize_instance=None,
    resolve_destination=None,
    allowed_position_accounts=None,
    _db=None,
):
    """Shared transaction for independently source-qualified native entry adapters."""
    if not callable(criterion_allowed):
        raise ValueError("Authoritative dungeon criterion evaluator required")
    if not callable(source_allowed):
        raise ValueError("Authoritative dungeon source check required")

    source = resolved["source"]
    route = resolved["route"]

    from wakfu_server import owned_physical_entry

    entry_policy = owned_physical_entry.entry_policy(store, route, db=_db)

    def authorize(character, selected_route):
        return (
            selected_route == route
            and source_allowed(character, dict(source)) is True
            and (
                owned_physical_entry.allowed(
                    store,
                    character,
                    route,
                    enforce_native_entry_criterion=entry_policy == "native",
                )
                if entry_policy is not None
                else criterion_allowed(character, route.criterion)
            )
            is True
        )

    difficulty_selection = resolved["difficulty_selection"]
    if difficulty_selection is None:
        from wakfu_server import dungeon_difficulty

        with store.connection() if _db is None else nullcontext(_db) as db:
            try:
                native = dungeon_difficulty.definition(db, route.definition_id)
            except ValueError:
                native = None
        if native is not None and native.get("difficulty_available", False):
            difficulty_selection = dict(
                stasis_level=max(2, native["minimum_stasis"]), competitive=False
            )

    def initialize_paid_instance(db, session):
        from wakfu_server.achievements import owned_quest_encounters

        owned_quest_encounters.initialize(db, session, resolved, store=store)
        # Story instances use their own multi-quest/room admission contract.
        # Import only an actually declared controller; absent code must never
        # downgrade a published story profile to an ordinary dungeon fight.
        story = db.execute(
            "SELECT 1 FROM dungeon_runtime_configurations WHERE route_key=%s "
            "AND policy_version=%s "
            "AND configuration->'topology'->'owned_story_controller' IS NOT NULL",
            (
                dungeon_instances.canonical_context_key(route),
                session["context_policy_version"],
            ),
        ).fetchone()
        if story is not None:
            from wakfu_server import owned_story_controller

            owned_story_controller.initialize(db, session, resolved, store=store)
        native = resolved["native_destination"]
        if (
            not session["reused"]
            and native.get("cyW", 0) > 0
            and native.get("item_reference", 0) > 0
        ):
            from .dungeon_entry_payment import consume

            session["entry_item_payment"] = consume(
                db, session["members"], native["item_reference"], native["cyW"]
            )
        from .special_instance_admission import initialize as initialize_special

        initialize_special(db, session, resolved)
        trials = db.execute(
            "SELECT 1 FROM dungeon_runtime_configurations WHERE route_key=%s "
            "AND policy_version=%s "
            "AND configuration->'topology'->'owned_object_trials' IS NOT NULL",
            (
                dungeon_instances.canonical_context_key(route),
                session["context_policy_version"],
            ),
        ).fetchone()
        if trials is not None:
            from wakfu_server.application import owned_object_trial_dispatch

            owned_object_trial_dispatch.initialize(db, session, resolved, store=store)
        if initialize_instance is not None:
            initialize_instance(db, session)

    with store.connection() if _db is None else nullcontext(_db) as db:
        native = resolved["native_destination"]
        if native.get("cyW", 0) > 0 and native.get("item_reference", 0) > 0:
            candidate = db.execute(
                "SELECT q.configuration FROM dungeon_runtime_active_configurations a "
                "JOIN dungeon_runtime_configurations q ON q.route_key=a.route_key "
                "AND q.policy_version=a.policy_version WHERE a.route_key=%s "
                "AND q.configuration->'topology'->>'policy'='owned-story-narrative-v1' "
                "AND q.configuration->'topology'->'rooms'='[]'::jsonb",
                (dungeon_instances.canonical_context_key(route),),
            ).fetchone()
            if candidate is not None:
                from wakfu_server import owned_story_reentry

                owned_story_reentry.prepare(
                    db,
                    store,
                    account_id,
                    generation,
                    character_id,
                    resolved,
                    candidate["configuration"],
                )
        session = dungeon_instances.create_or_reuse(
            store,
            account_id,
            generation,
            character_id,
            route.key,
            authorize_entry=authorize,
            difficulty_selection=difficulty_selection,
            initialize_instance=initialize_paid_instance,
            resolve_destination=resolve_destination,
            transition_destination={
                key: resolved["destination"][key] for key in ("map_id", "x", "y", "z")
            },
            allowed_position_accounts=allowed_position_accounts,
            _db=db,
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
    positions=None,
):
    """Enter with a party-wide position barrier when a live buffer is supplied."""

    def transition(allowed_accounts=None):
        return _enter(
            store,
            account_id,
            generation,
            character_id,
            entry_map_id,
            body,
            criterion_allowed=criterion_allowed,
            source_allowed=source_allowed,
            initialize_instance=initialize_instance,
            resolve_destination=resolve_destination,
            allowed_position_accounts=allowed_accounts,
        )

    if positions is None:
        return transition()
    from .dungeon_position_barrier import run_party_entry

    return run_party_entry(
        store,
        positions,
        account_id,
        character_id,
        transition=transition,
    )
