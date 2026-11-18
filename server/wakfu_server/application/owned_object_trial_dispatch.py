"""Opt-in session bridge for native owned puzzles without ordinary fights."""

import struct
from uuid import uuid4

from wakfu_server import owned_object_trials as trials
from wakfu_server.owned_object_trial_effects import executor


def _configuration(db, character):
    if (
        not character.get("instance_id")
        or character.get("map_id") not in trials.trial_maps()
    ):
        return None
    from wakfu_server import dungeon_runtime

    marker = db.execute(
        "SELECT q.configuration->'topology'->'owned_object_trials' AS marker "
        "FROM dungeon_instances i JOIN dungeon_runtime_configurations q "
        "ON q.route_key=i.context_route_key AND q.policy_version=i.context_policy_version "
        "WHERE i.instance_id=%s",
        (character["instance_id"],),
    ).fetchone()
    if marker is None or marker["marker"] is None:
        return None
    return dungeon_runtime.configuration_for_instance(db, character["instance_id"])[1]


def initialize(db, session, resolved, *, store):
    """Initialize only native presentation; quests are never assigned here."""
    from wakfu_server import companions

    members = list(session["members"])
    if len(members) != 1 or companions.controlled_count(db, members):
        raise ValueError("Owned object context requires its one original owner")
    owner = db.execute(
        "SELECT account_id FROM characters WHERE id=%s", (members[0],)
    ).fetchone()
    if owner is None:
        raise ValueError("Owned object context owner no longer exists")
    character = store.character(owner["account_id"], members[0], db)
    selected, current = trials._scope(db, store, character)
    trials.cancel_pending(db, current, selected)
    key = f'owned-object-trial:{selected["id"]}:{current["instance_id"]}:initialize'
    if (
        db.execute(
            "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
            (current["id"], key),
        ).fetchone()
        is not None
    ):
        return
    # Delivery occurs after normal bootstrap. Do not consume the global once
    # marker before an actual loaded owner can receive the native scene.
    trials.storage.record_event(
        db,
        current["id"],
        key,
        dict(
            schema=trials.SCHEMA,
            owner=current["id"],
            instance_id=current["instance_id"],
            state=trials.initial_state(selected),
            event=dict(kind="initialize"),
            presentation_due_ms=0,
        ),
    )


def hydrate(session):
    state, runtime = session.state, session.runtime
    state.connection.owned_object_trials_active = False
    if (
        state.character is None
        or not state.loaded
        or not state.character.get("instance_id")
    ):
        return False
    with runtime.STORE.connection() as db:
        configuration = _configuration(db, state.character)
        if configuration is None:
            return False
        trials.snapshot(db, runtime.STORE, state.character)
        selected = trials.policy(configuration)
        state.connection.owned_object_trial_timer = any(
            row["kind"] == "light_course" for row in selected["trials"]
        )
        state.connection.owned_object_trial_poll_ms = 0
    state.connection.owned_object_trials_active = True
    return True


def _publish(session, character, packets):
    state, runtime = session.state, session.runtime
    previous = state.character
    state.character = character
    if any(
        previous.get(key) != character[key]
        for key in ("map_id", "instance_id", "x", "y", "z")
    ):
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, character["id"]
        )
        state.position = {key: character[key] for key in ("x", "y", "z")}
        state.movement_state = runtime.Movement(state.position)
        for opcode, body in packets:
            if opcode == 13530:
                runtime.WORLD.update(
                    state.generation, character, opcode, body, include_sender=False
                )
        session.mark_static_sync_pending()
    session.publish_settled_quest_packets(packets)


def projection(db, store, character, selected, *, restore=False):
    """Hydrate persisted native gates/guards after loading or a real action."""
    from wakfu_server import owned_world_light_program
    from . import owned_world_stealth_actor_dispatch

    durable = trials._load_state(db, character, selected)
    effects = []
    for trial in selected["trials"]:
        if trial["kind"] == "light_course":
            current = durable["trials"].get(trial["id"], {})
            effects.extend(owned_world_light_program.gate_effects(trial, current))
            if restore:
                effects.extend(
                    owned_world_light_program.reconnect_effects(
                        trial, current, now_ms=int(store.now().timestamp() * 1000)
                    )
                )
    packets = list(executor(selected)(db, store, character, effects))
    packets.extend(
        owned_world_stealth_actor_dispatch.render(selected, durable, character)
    )
    return packets


def handle_interaction(session):
    state, runtime = session.state, session.runtime
    if state.opcode != 12870 or not getattr(
        state.connection, "owned_object_trials_active", False
    ):
        return False
    if not isinstance(state.body, bytes) or len(state.body) != 12:
        return False
    if session.environment_blocked():
        raise ValueError(
            "Owned object trial action is unavailable during an occupation"
        )
    from wakfu_server.environment_interactions import _guard

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            configuration = _configuration(db, current)
            if configuration is None:
                state.connection.owned_object_trials_active = False
                return False
            selected = trials.policy(configuration)
            source_id = struct.unpack_from(">q", state.body)[0]
            if source_id not in {row["id"] for row in selected["sources"]}:
                return False
            _guard(db, current["id"])
            result = trials.interact(
                db,
                runtime.STORE,
                current,
                state.body,
                token=uuid4().hex,
                generation=state.generation,
                apply_effects=executor(selected),
            )
            character = runtime.STORE.character(state.account_id, current["id"], db)
            if result["changed"]:
                result["packets"].extend(
                    projection(db, runtime.STORE, character, selected)
                )
        state.connection.owned_object_trial_pending = result.get("pending")
        _publish(session, character, result["packets"])
    return True


def ready(session):
    """Offer the native entry presentation only to an actually loaded owner."""
    state, runtime = session.state, session.runtime
    if (
        not state.loaded
        or state.character is None
        or not getattr(state.connection, "owned_object_trials_active", False)
        or not state.character.get("instance_id")
        or state.character.get("map_id") not in trials.trial_maps()
    ):
        return
    identity = (state.character["id"], state.character["instance_id"])
    if getattr(state.connection, "owned_object_trial_ready", None) == identity:
        return
    from wakfu_server.inventory_items import _lease
    from wakfu_server.environment_interactions import _guard

    packets = []
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            _lease(runtime.STORE, db, state.account_id, state.generation, current["id"])
            _guard(db, current["id"])
            selected, _ = trials._scope(db, runtime.STORE, current)
            key = f'owned-object-trial:{selected["id"]}:{current["instance_id"]}:ready'
            if (
                db.execute(
                    "SELECT 1 FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                    (current["id"], key),
                ).fetchone()
                is None
            ):
                applied = executor(selected)(
                    db, runtime.STORE, current, selected.get("entry_effects", ())
                )
                packets = list(applied)
                trials.storage.record_event(
                    db,
                    current["id"],
                    key,
                    dict(
                        schema=trials.SCHEMA,
                        owner=current["id"],
                        instance_id=current["instance_id"],
                        state=trials._load_state(db, current, selected),
                        event=dict(kind="ready"),
                        presentation_due_ms=getattr(applied, "presentation_due_ms", 0),
                    ),
                )
            packets.extend(
                projection(db, runtime.STORE, current, selected, restore=True)
            )
    state.connection.owned_object_trial_ready = identity
    if packets:
        session.publish_settled_quest_packets(packets)


def poll(session):
    state, runtime = session.state, session.runtime
    if (
        not getattr(state.connection, "owned_object_trials_active", False)
        or not state.loaded
        or state.character is None
        or state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
    ):
        return
    if (
        not state.character.get("instance_id")
        or state.character.get("map_id") not in trials.trial_maps()
    ):
        state.connection.owned_object_trials_active = False
        state.connection.owned_object_trial_pending = None
        state.connection.owned_object_trial_ready = None
        return
    ready(session)
    # Only an active timed declaration polls its persisted deadline. Other
    # owned trials keep their unchanged pending-occupation scheduling.
    if getattr(state.connection, "owned_object_trial_timer", None) is None:
        with runtime.STORE.connection() as db:
            configuration = _configuration(db, state.character)
            selected = (
                trials.policy(configuration) if configuration is not None else None
            )
            state.connection.owned_object_trial_timer = bool(
                selected is not None
                and any(row["kind"] == "light_course" for row in selected["trials"])
            )
    now_ms = int(runtime.STORE.now().timestamp() * 1000)
    if state.connection.owned_object_trial_timer and now_ms >= getattr(
        state.connection, "owned_object_trial_poll_ms", 0
    ):
        state.connection.owned_object_trial_poll_ms = now_ms + 1000
        from wakfu_server.inventory_items import _lease

        with runtime.POSITIONS.account_barrier(state.account_id):
            runtime.flush_positions(
                account_id=state.account_id,
                generation=state.generation,
                character_id=state.character["id"],
            )
            with runtime.STORE.connection() as db:
                current = runtime.STORE.character(
                    state.account_id, state.character["id"], db
                )
                _lease(
                    runtime.STORE, db, state.account_id, state.generation, current["id"]
                )
                selected, _ = trials._scope(db, runtime.STORE, current)
                result = trials.due_tick(
                    db,
                    runtime.STORE,
                    current,
                    token=uuid4().hex,
                    apply_effects=executor(selected),
                )
                character = runtime.STORE.character(state.account_id, current["id"], db)
            if result["changed"]:
                _publish(session, character, result["packets"])
    pending = getattr(state.connection, "owned_object_trial_pending", None)
    if pending is None or runtime.STORE.now().timestamp() * 1000 < pending["due_ms"]:
        return
    if state.fight is not None or state.combat_session is not None:
        return
    from wakfu_server.environment_interactions import _guard

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            if current["instance_id"] != pending["instance_id"]:
                state.connection.owned_object_trial_pending = None
                return
            selected, _ = trials._scope(db, runtime.STORE, current)
            _guard(db, current["id"])
            result = trials.complete_interaction(
                db,
                runtime.STORE,
                current,
                pending["token"],
                generation=state.generation,
                apply_effects=executor(selected),
            )
            character = runtime.STORE.character(state.account_id, current["id"], db)
            result["packets"].extend(projection(db, runtime.STORE, character, selected))
        state.connection.owned_object_trial_pending = None
        _publish(session, character, result["packets"])


def arm_movement(session, path):
    """Observe the whole accepted path durably, including redirect/loop moves.

    Logical positions already committed by the normal movement owner are
    flushed before this observer; it never validates or invents a movement.
    """
    state, runtime = session.state, session.runtime
    if not getattr(state.connection, "owned_object_trials_active", False):
        return
    from wakfu_server.inventory_items import _lease
    from wakfu_server.environment_interactions import _guard

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            configuration = _configuration(db, current)
            if configuration is None:
                state.connection.owned_object_trials_active = False
                return
            _lease(runtime.STORE, db, state.account_id, state.generation, current["id"])
            _guard(db, current["id"])
            selected = trials.policy(configuration)
            result = trials.on_landing(
                db,
                runtime.STORE,
                current,
                [[point[key] for key in ("x", "y", "z")] for point in path],
                token=uuid4().hex,
                apply_effects=executor(selected),
            )
            character = runtime.STORE.character(state.account_id, current["id"], db)
            if result["changed"]:
                result["packets"].extend(
                    projection(db, runtime.STORE, character, selected)
                )
        if result.get("cancelled_occupation"):
            state.connection.owned_object_trial_pending = None
        _publish(session, character, result["packets"])


def handle_travel(session, configuration, *, source_allowed, in_fight):
    if trials.policy(configuration) is None:
        return False
    state, runtime = session.state, session.runtime
    from wakfu_server import owned_quest_transfers

    source_id = struct.unpack_from(">q", state.body)[0]
    selected = trials.policy(configuration)
    requirements = selected.get("travel_requirements", {}).get(str(source_id), ())
    if requirements:
        with runtime.STORE.connection() as db:
            selected, current = trials._scope(
                db, runtime.STORE, state.character, lock=False
            )
            durable = trials._load_state(db, current, selected)
            if any(
                durable["trials"].get(identity, {}).get("complete") is not True
                for identity in requirements
            ):
                raise ValueError(
                    "Complete the physical challenge before using its far exit"
                )

    declaration = owned_quest_transfers.selection(configuration["topology"], state.body)
    if declaration is not None:
        from wakfu_server import (
            generic_transports,
            dungeon_runtime,
            dungeon_entry_access,
        )
        from wakfu_server.combat_terrain import map_geometry

        source_id, destination_id, _, _ = struct.unpack(">qiBi", state.body)
        source = generic_transports.source(state.character["map_id"], source_id)
        destination = next(
            row
            for row in source["destinations"]
            if row["destination_id"] == destination_id
        )
        owned_quest_transfers.transfer(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character["id"],
            state.body,
            source_allowed=source_allowed,
            in_fight=in_fight,
            criterion_allowed=lambda actor, criterion: dungeon_entry_access.evaluate(
                runtime.STORE,
                criterion,
                character=actor,
                destination_map_id=destination["map_id"],
            ),
            initialize_instance=lambda db, admitted: dungeon_runtime.initialize_instance(
                db,
                admitted,
                groups=runtime.COMBAT_GROUPS,
                geometry=map_geometry(destination["map_id"]),
                store=runtime.STORE,
            ),
            resolve_destination=dungeon_runtime.entry_destination,
            positions=runtime.POSITIONS,
        )
        state.connection.owned_object_trials_active = False
        state.connection.owned_object_trial_pending = None
        session.deliver_dungeon_transitions(before_action=True)
        return True
    from wakfu_server import owned_story_exits, dungeon_exit
    from wakfu_server.inventory_items import _lease

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            _lease(runtime.STORE, db, state.account_id, state.generation, current["id"])
            authenticated = owned_story_exits.authenticate_exit(
                db, runtime.STORE, current, state.body, source_allowed=source_allowed
            )
            selected, _ = trials._scope(db, runtime.STORE, current)
            trials.cancel_pending(db, current, selected)
            destination = {
                key: authenticated["destination"][key]
                for key in ("map_id", "x", "y", "z")
            }
            dungeon_exit._leave(
                runtime.STORE,
                state.account_id,
                state.generation,
                current["id"],
                in_fight=in_fight,
                destination_for=lambda *_: destination,
                _db=db,
            )
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, current["id"]
        )
    state.connection.owned_object_trial_pending = None
    state.connection.owned_object_trials_active = False
    session.deliver_dungeon_transitions(before_action=True)
    return True
