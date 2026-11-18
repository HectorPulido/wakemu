"""Session adapters for declared private room stories and their native effects.

Unrelated scenes have no marker and retain their existing dispatch. Every
mutation uses the normal account position fence, lease, idle guard and shared
quest publication; no client-facing progress command is added.
"""

import struct
import time
from uuid import uuid4

from wakfu_server import owned_story_controller as controller
from wakfu_server import owned_story_mechanics as mechanics


def _configuration(db, character):
    if not controller.recognizes_instance(db, character.get("instance_id")):
        return None
    from wakfu_server import dungeon_runtime

    return dungeon_runtime.configuration_for_instance(db, character["instance_id"])[1]


def _result(db, store, character, outcome):
    # Native transfers and skipped-scene continuations may move inside this tx.
    character = store.character(character["account_id"], character["id"], db)
    selected, completed = controller._scope(db, store, character)
    pending = controller.pending_scene(db, store, character, selected, completed)
    return dict(
        outcome,
        character=character,
        handled=True,
        completed=[],
        pending_scene=pending,
    )


def interact(store, account_id, generation, location, body, *, loaded, blocked):
    if blocked or not loaded or not isinstance(body, bytes) or len(body) != 12:
        raise ValueError("Owned story interaction is unavailable")
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard
    from wakfu_server.simple_item_actions import _idle

    object_id, action, parameter = struct.unpack(">qHH", body)
    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        _guard(db, location["id"])
        character = store.character(account_id, location["id"], db)
        _idle(db, character["id"], store.now())
        selected, completed = controller._scope(db, store, character)
        if (
            controller.pending_scene(db, store, character, selected, completed)
            is not None
        ):
            raise ValueError("The owned story cinematic is still pending")
        from wakfu_server import owned_story_dynamic_pickups

        pickup = owned_story_dynamic_pickups.interact(db, store, character, body)
        if pickup is not None:
            return _result(db, store, character, pickup)
        transfers = [
            row
            for row in selected.get("native_transfers", ())
            if row["source_id"] == object_id
        ]
        if transfers:
            if action or parameter or not set(transfers[0]["requires"]) <= completed:
                raise ValueError("Owned artifact travel is not unlocked")
            native = next(
                (
                    row
                    for row in mechanics.sources(selected)["objects"]
                    if row["id"] == object_id
                ),
                None,
            )
            if (
                native is None
                or abs(character["z"] - native["z"]) > 1
                or abs(character["x"] - native["x"]) + abs(character["y"] - native["y"])
                > 1
            ):
                raise ValueError("Owned artifact travel is outside its native approach")
            packets = mechanics.native_transfer(
                db,
                store,
                character,
                selected,
                object_id,
                transfers[0]["effect_reference"],
            )
            return _result(
                db, store, character, dict(applied=True, packets=packets, step=None)
            )
        from wakfu_server import owned_companion_rescue

        rescue_packets = []
        rescue = owned_companion_rescue.policy(selected)
        if rescue is not None and object_id == rescue["source_id"]:
            # Existing owners may first encounter the optional rescue on a later visit.
            rescue_packets.extend(
                owned_companion_rescue.admit(db, store, character, selected)
            )
        visuals = mechanics.object_visuals(
            db, store, character, selected, object_id, action
        )
        rescue_packets.extend(
            owned_companion_rescue.interact(
                db, store, character, selected, object_id, action
            )
        )
        outcome = controller.interact(
            db, store, character, body, apply_effects=mechanics.executor(selected)
        )
        if not outcome["applied"] and object_id in selected.get(
            "recoverable_native_loot", ()
        ):
            # A once-earned discovery stays earned; its native empty-inventory
            # pickup can still recover an item destroyed or consumed later.
            recoverable = [
                effect
                for step in selected["steps"]
                if step["id"] in completed
                and step["kind"] == "interactive"
                and step["reference"] == object_id
                for effect in step["effects"]
                if effect["kind"] == "native_loot"
                and effect.get("source_id") == object_id
            ]
            if recoverable:
                outcome["packets"].extend(
                    mechanics.executor(selected)(db, store, character, recoverable)
                )
        if (
            not outcome["applied"]
            and not visuals
            and not any(
                step["kind"] == "interactive"
                and step["reference"] == object_id
                and step["id"] in completed
                for step in selected["steps"]
            )
        ):
            raise ValueError("Complete the current room before using this object")
        outcome["packets"] = visuals + rescue_packets + outcome["packets"]
        return _result(db, store, character, outcome)


def callback(store, account_id, generation, location, body, *, pending_step, blocked):
    if blocked:
        raise ValueError("Owned story scene is unavailable during combat")
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard

    with store.connection() as db:
        _leased_owner(store, db, account_id, generation, location)
        _guard(db, location["id"])
        current = store.character(account_id, location["id"], db)
        selected, _ = controller._scope(db, store, current)
        outcome = controller.on_scene_complete(
            db,
            store,
            current,
            body,
            pending_step=pending_step,
            apply_effects=mechanics.executor(selected),
        )
        return _result(db, store, current, outcome)


def publish(session, result):
    state, runtime = session.state, session.runtime
    previous = state.character
    state.character = result["character"]
    moved = any(
        previous.get(key) != state.character.get(key)
        for key in ("map_id", "instance_id", "x", "y", "z")
    )
    if moved:
        state.position = {key: state.character[key] for key in ("x", "y", "z")}
        state.movement_state = runtime.Movement(state.position)
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, state.character["id"]
        )
        for packet in result["packets"]:
            if packet[0] == 13530:
                runtime.WORLD.update(
                    state.generation, state.character, *packet, include_sender=False
                )
        session.mark_static_sync_pending()
    pending = result.get("pending_scene")
    if any(packet[0] == 13411 for packet in result["packets"]):
        state.connection.pending_owned_story_scene = (
            None if pending is None else pending["marker"]
        )
    elif pending is None:
        state.connection.pending_owned_story_scene = None
    state.connection.owned_story_poll_due = 0
    session.publish_settled_quest_packets(result["packets"])
    refresh_group(session)


def _handle_interaction(session):
    state, runtime = session.state, session.runtime
    if state.opcode != 12870 or not state.character.get("instance_id"):
        return False
    with runtime.STORE.connection() as db:
        configuration = _configuration(db, state.character)
        if configuration is None:
            return False
        from wakfu_server import owned_story_generic_transfer
        from wakfu_server import owned_story_generic_return

        if owned_story_generic_return.selection(configuration, state.body) is not None:
            return False  # The shared timed entry adapter owns the public return.
        if (
            owned_story_generic_transfer.selection(configuration, state.body)
            is not None
        ):
            return False  # The shared entry adapter owns the atomic private handoff.
        if len(state.body) == 12 and struct.unpack_from(">q", state.body)[0] in {
            row["source_id"]
            for row in configuration["topology"].get("native_story_exits", ())
        }:
            return False
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        from wakfu_server import owned_story_object_operations

        if owned_story_object_operations.begin(session):
            return True
        result = interact(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character,
            state.body,
            loaded=state.loaded,
            blocked=session.environment_blocked()
            or state.environment_ticket is not None,
        )
        publish(session, result)
    return True


def handle_callback(session):
    state, runtime = session.state, session.runtime
    marker = getattr(state.connection, "pending_owned_story_scene", None)
    if marker is None:
        return False
    if marker[0] != state.character.get("instance_id"):
        state.connection.pending_owned_story_scene = None
        return False
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(account_id=state.account_id)
        result = callback(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character,
            state.body,
            pending_step=marker,
            blocked=state.fight is not None or state.combat_session is not None,
        )
        publish(session, result)
    return True


def _visible_ids(selected, character, chunks=None):
    from wakfu_server.world_scene_sync import chunk, neighborhood

    if chunks is None:
        chunks = neighborhood(chunk(character))
    return {
        row["id"]
        for row in mechanics.sources(selected)["objects"]
        if tuple(map(int, row["chunk"].split("_"))) in chunks
    }


def hydrate(session, *, chunks=None):
    """Restore only registered native objects, without replaying story scenes."""
    from . import owned_object_trial_dispatch

    owned_object_trial_dispatch.hydrate(session)
    state, runtime = session.state, session.runtime
    if stage_ready(session):
        state.connection.owned_story_active = False
        return True
    if not state.character.get("instance_id"):
        state.connection.owned_story_active = False
        state.connection.owned_presentation_context = None
        return False
    with runtime.STORE.connection() as db:
        configuration = _configuration(db, state.character)
        if configuration is None:
            state.connection.owned_story_active = False
            state.connection.owned_presentation_context = None
            return False
        selected, completed = controller._scope(
            db, runtime.STORE, state.character, check_position=False, lock=False
        )
        if mechanics.sources(selected).get("presentation_groups"):
            from wakfu_server.achievements import tutorial_presentation_once

            context = getattr(state.connection, "owned_presentation_context", None)
            if context is None or context[0] != state.character["instance_id"]:
                context = (state.character["instance_id"], uuid4().hex)
                state.connection.owned_presentation_context = context
            tutorial_presentation_once.register_context(db, state.character, context[1])
        visible = _visible_ids(selected, state.character, chunks)
        packets = [
            packet
            for packet in controller.element_packets(selected, completed)
            if struct.unpack_from(">q", packet[1])[0] in visible
        ]
        if mechanics.sources(selected).get("scene_actors"):
            from wakfu_server.owned_story_admission import scene_actor_packets

            packets.extend(scene_actor_packets(db, runtime.STORE, state.character))
        if mechanics.sources(selected).get("reviewed_dynamic_pickups"):
            from wakfu_server import owned_story_dynamic_pickups

            packets.extend(
                owned_story_dynamic_pickups.packets(db, runtime.STORE, state.character)
            )
        from wakfu_server import owned_story_traps

        traps = owned_story_traps.projection(
            db,
            runtime.STORE,
            runtime.STORE.character(state.account_id, state.character["id"], db),
            configuration,
            initialize=False,
        )
        if traps["active"]:
            projection = dict(
                selected,
                initial_elements=[],
                steps=[dict(id="trap", effects=traps["state_effects"])],
            )
            packets.extend(
                packet
                for packet in controller.element_packets(projection, {"trap"})
                if struct.unpack_from(">q", packet[1])[0] in visible
            )
    runtime.send_batch(state.connection, state.service, packets)
    state.connection.owned_story_terminal_returns = (
        selected.get("terminal_returns") is not None
    )
    state.connection.owned_story_active = True
    state.connection.owned_story_poll_due = 0
    return True


def arm_movement(session, path):
    """Delay owned zone/hazard observation until the accepted walk completes."""
    from . import owned_object_trial_dispatch

    owned_object_trial_dispatch.arm_movement(session, path)
    state = session.state
    if not getattr(state.connection, "owned_story_active", False):
        return
    state.connection.owned_story_arrival = dict(
        instance_id=state.character["instance_id"],
        position=tuple(path[-1][key] for key in ("x", "y", "z")),
        token="owned-path:" + uuid4().hex,
        due=time.monotonic() + max(0, len(path) - 1) * 0.5 + 0.1,
    )
    state.connection.owned_story_poll_due = 0


def poll(session):
    """Advance literal scene/fall deadlines and periodic native trap phases."""
    from wakfu_server import owned_story_actor_healing
    from wakfu_server import owned_story_object_operations
    from . import owned_object_trial_dispatch

    owned_story_actor_healing.poll(session)
    owned_story_object_operations.poll(session)
    owned_object_trial_dispatch.poll(session)
    state, runtime = session.state, session.runtime
    if stage_poll(session):
        return
    if (
        not getattr(state.connection, "owned_story_active", False)
        or not state.loaded
        or state.character is None
        or state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
    ):
        return
    now = time.monotonic()
    if now < getattr(state.connection, "owned_story_poll_due", 0):
        return
    if getattr(state.connection, "owned_story_terminal_returns", False):
        from wakfu_server import owned_story_terminal_returns

        if owned_story_terminal_returns.poll(session):
            return
    arrival = getattr(state.connection, "owned_story_arrival", None)
    if arrival is not None and now < arrival["due"]:
        state.connection.owned_story_poll_due = arrival["due"]
        return
    from wakfu_server.paid_containers import _leased_owner
    from wakfu_server.environment_interactions import _guard
    from wakfu_server import owned_story_traps

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            _leased_owner(
                runtime.STORE, db, state.account_id, state.generation, state.character
            )
            _guard(db, state.character["id"])
            current = runtime.STORE.character(
                state.account_id, state.character["id"], db
            )
            configuration = _configuration(db, current)
            if configuration is None:
                state.connection.owned_story_active = False
                state.connection.pending_owned_story_scene = None
                state.connection.owned_story_arrival = None
                return
            selected, completed = controller._scope(db, runtime.STORE, current)
            packets = mechanics.complete_reset(db, runtime.STORE, current, selected)
            if any(opcode == 13530 for opcode, _ in packets):
                current = runtime.STORE.character(state.account_id, current["id"], db)
            ready = controller.on_world_ready(db, runtime.STORE, current)
            packets.extend(ready["packets"])
            from wakfu_server import owned_story_resource_slots

            packets.extend(
                owned_story_resource_slots.ensure(
                    db, runtime.STORE, current, selected, configuration
                )
            )
            outcome = controller.complete_due_scene(db, runtime.STORE, current)
            packets.extend(outcome["packets"])
            if outcome["applied"]:
                current = runtime.STORE.character(state.account_id, current["id"], db)
            selected, completed = controller._scope(db, runtime.STORE, current)
            if arrival is not None:
                state.connection.owned_story_arrival = None
                if arrival["instance_id"] == current["instance_id"] and arrival[
                    "position"
                ] == tuple(current[k] for k in ("x", "y", "z")):
                    from wakfu_server import native_interactive_activation

                    native = next(
                        (
                            row
                            for row in mechanics.sources(selected)["objects"]
                            if row["type"] == "ZoneTrigger"
                            and arrival["position"]
                            in set(
                                map(tuple, native_interactive_activation.decode(row))
                            )
                        ),
                        None,
                    )
                    if native is not None:
                        observed = controller.on_zone_trigger(
                            db,
                            runtime.STORE,
                            current,
                            native["id"],
                            apply_effects=mechanics.executor(selected),
                        )
                        packets.extend(observed["packets"])
                        if observed["applied"]:
                            current = runtime.STORE.character(
                                state.account_id, current["id"], db
                            )
                            selected, completed = controller._scope(
                                db, runtime.STORE, current
                            )
            pending = controller.pending_scene(
                db, runtime.STORE, current, selected, completed
            )
            trap_projection = owned_story_traps.projection(
                db, runtime.STORE, current, configuration
            )
            if pending is None and mechanics.pending_reset(db, current) is None:

                def fall_effects(inner_db, inner_store, actor, projection):
                    return [
                        mechanics.scenario_packet(
                            selected, projection["reset"]["native_event"]
                        )
                    ]

                fall = owned_story_traps.on_tick(
                    db,
                    runtime.STORE,
                    current,
                    configuration,
                    apply_effects=fall_effects,
                )
                packets.extend(fall["packets"])
            if trap_projection["active"]:
                phase = trap_projection["phase"]
                if getattr(state.connection, "owned_story_trap_phase", None) != phase:
                    projection = dict(
                        selected,
                        initial_elements=[],
                        steps=[
                            dict(id="trap", effects=trap_projection["state_effects"])
                        ],
                    )
                    visible = _visible_ids(selected, current)
                    packets.extend(
                        packet
                        for packet in controller.element_packets(projection, {"trap"})
                        if struct.unpack_from(">q", packet[1])[0] in visible
                    )
                    state.connection.owned_story_trap_phase = phase
            result = _result(
                db,
                runtime.STORE,
                current,
                dict(applied=bool(packets), packets=packets, step=None),
            )
            now_ms = int(runtime.STORE.now().timestamp() * 1000)
            deadlines = [now_ms + 1000]
            if result["pending_scene"] is not None:
                deadlines.append(result["pending_scene"]["due_ms"])
            falling = mechanics.pending_reset(db, current)
            if falling is not None:
                deadlines.append(falling["payload"]["reset"]["due_ms"])
            if trap_projection["active"]:
                deadlines.append(trap_projection["next_transition_ms"])
        if packets or ready["applied"] or outcome["applied"]:
            publish(session, result)
        else:
            # A real story step can unlock a formation while combat return
            # owns the socket. Recover that durable frontier once after idle
            # hydration for ordinary rooms as well as automatic ambushes.
            frontier = (current["instance_id"], tuple(sorted(completed)))
            if selected.get("automatic_room_start") is not None:
                from wakfu_server import owned_story_auto_start

                frontier += (
                    owned_story_auto_start.ready_room_orders(configuration, current),
                )
            if getattr(state.connection, "owned_story_auto_frontier", None) != frontier:
                state.connection.owned_story_auto_frontier = frontier
                refresh_group(session)
        state.connection.owned_story_poll_due = time.monotonic() + max(
            0.05, (min(deadlines) - now_ms) / 1000
        )


def refresh_group(session):
    """Publish a newly unlocked actual native formation after its owning step."""
    state, runtime = session.state, session.runtime
    if not state.character.get("instance_id") or state.fight is not None:
        return
    from wakfu_server import dungeon_runtime
    from wakfu_server.combat_terrain import map_geometry

    with runtime.STORE.connection() as db:
        configuration = _configuration(db, state.character)
        if configuration is None:
            return
        pool_spawns = []
        group = dungeon_runtime.ensure_current_room(
            db,
            runtime.COMBAT_GROUPS,
            state.character["instance_id"],
            map_geometry(state.character["map_id"]),
            quest_pool_spawns=pool_spawns,
        )
    for pool in pool_spawns:
        runtime.WORLD.emit_location(
            state.character["map_id"],
            state.character["instance_id"],
            12608,
            runtime.owned_scene_spawn_group(pool["members"], group_id=pool["group_id"]),
        )
    if group is not None and group.get("replay") is False:
        runtime.WORLD.emit_location(
            state.character["map_id"],
            state.character["instance_id"],
            12608,
            runtime.owned_scene_spawn_group(
                group["members"], group_id=group["group_id"]
            ),
        )

    if group is not None:
        from wakfu_server import owned_story_admission

        packets = owned_story_admission.observe_room_available(
            runtime.STORE, state.character
        )
        if packets:
            with runtime.STORE.connection() as db:
                current = runtime.STORE.character(
                    state.account_id, state.character["id"], db
                )
                result = _result(
                    db,
                    runtime.STORE,
                    current,
                    dict(applied=True, packets=packets, step=None),
                )
            publish(session, result)

    if group is not None:
        from wakfu_server import owned_story_auto_start

        owned_story_auto_start.queue(session, group, configuration=configuration)


def handle_travel(session, configuration, *, source_allowed, in_fight):
    """Preserve native paid owned transfers and literal conditional story exits."""
    state, runtime = session.state, session.runtime
    if (
        configuration.get("topology", {}).get("owned_object_trials") is not None
        and configuration.get("topology", {}).get("owned_story_controller") is None
    ):
        from wakfu_server.application import owned_object_trial_dispatch

        return owned_object_trial_dispatch.handle_travel(
            session, configuration, source_allowed=source_allowed, in_fight=in_fight
        )
    from wakfu_server import (
        owned_quest_transfers,
        dungeon_runtime,
        dungeon_entry_access,
    )
    from wakfu_server.combat_terrain import map_geometry

    if (
        owned_quest_transfers.selection(configuration["topology"], state.body)
        is not None
    ):
        from wakfu_server import generic_transports

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
        session.deliver_dungeon_transitions(before_action=True)
        return True
    selected = controller.policy(configuration)
    if selected is None:
        return False
    if selected.get("native_links"):
        from wakfu_server import owned_story_native_links

        if owned_story_native_links.selected_link(selected, state.body) is not None:
            return owned_story_native_links.handle_session(
                session, source_allowed=source_allowed, in_fight=in_fight
            )
    from wakfu_server import (
        owned_story_exits,
        owned_cinematic_continuations,
        dungeon_exit,
    )

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
            authenticated = owned_story_exits.authenticate_exit(
                db, runtime.STORE, current, state.body, source_allowed=source_allowed
            )
            continuation = owned_cinematic_continuations.policy(
                authenticated["controller"]
            )
            if (
                continuation is not None
                and authenticated["destination"]["map_id"]
                == continuation["stage"]["map_id"]
            ):
                owned_cinematic_continuations.begin(
                    db,
                    runtime.STORE,
                    state.account_id,
                    state.generation,
                    current["id"],
                    state.body,
                    source_allowed=source_allowed,
                    in_fight=in_fight,
                )
            else:
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
            state.account_id, state.generation, state.character["id"]
        )
    session.deliver_dungeon_transitions(before_action=True)
    return True


def handle_interaction(session):
    try:
        from . import owned_object_trial_dispatch

        if owned_object_trial_dispatch.handle_interaction(session):
            return True
        return _handle_interaction(session)
    except ValueError as error:
        from wakfu_server.ecology_feedback import information

        session.runtime.record(
            event="owned_story_interaction_rejected",
            actor_id=session.state.character["id"],
            reason=str(error),
        )
        session.runtime.send(
            session.state.connection, session.state.service, *information(str(error))
        )
        return True


def stage_ready(session):
    """Start an owned cinematic stage only after its ordinary map bootstrap."""
    from wakfu_server import owned_cinematic_continuations

    state, runtime = session.state, session.runtime
    if (
        not owned_cinematic_continuations.owns_stage(state.character)
        or not state.loaded
    ):
        return False
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            result = owned_cinematic_continuations.ready(
                db,
                runtime.STORE,
                state.account_id,
                state.generation,
                state.character["id"],
            )
    if result is None:
        return False
    state.connection.owned_cinematic_active = True
    state.connection.owned_cinematic_due_ms = result["due_ms"]
    runtime.send_batch(state.connection, state.service, result["packets"])
    return True


def stage_poll(session):
    """Retain the normal exit/outbox delivery on both sides of the native scene."""
    state, runtime = session.state, session.runtime
    if not getattr(state.connection, "owned_cinematic_active", False):
        return False
    from wakfu_server import owned_cinematic_continuations

    if state.character is None:
        state.connection.owned_cinematic_active = False
        return False
    if not owned_cinematic_continuations.owns_stage(state.character):
        state.connection.owned_cinematic_active = False
        return False
    if not state.loaded or state.fight is not None:
        return True
    if (
        int(runtime.STORE.now().timestamp() * 1000)
        < state.connection.owned_cinematic_due_ms
    ):
        return True
    from wakfu_server import owned_cinematic_continuations

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )
        with runtime.STORE.connection() as db:
            result = owned_cinematic_continuations.finish(
                db,
                runtime.STORE,
                state.account_id,
                state.generation,
                state.character["id"],
            )
        if result is None:
            return True
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, state.character["id"]
        )
        runtime.send_batch(
            state.connection, state.service, result["before_transition_packets"]
        )
    state.connection.owned_cinematic_active = False
    session.deliver_dungeon_transitions(before_action=True)
    return True
