"""Declared normal exterior returns after genuine settled owned room outcomes."""

from collections import Counter

from wakfu_server.achievements import storage

SCHEMA = "owned-story-terminal-return-v1"
STEP_SCHEMA = "owned-story-step-return-v1"


def _step_destination(selected, value):
    if (
        not {
            "schema",
            "after_steps",
            "source_map_id",
            "source_id",
            "source_sha256",
            "destination_id",
            "evidence",
        }
        <= set(value)
        or set(value)
        - {
            "schema",
            "after_steps",
            "source_map_id",
            "source_id",
            "source_sha256",
            "destination_id",
            "evidence",
            "defeat_room_orders",
            "loss_events",
        }
        or not isinstance(value["after_steps"], list)
        or not value["after_steps"]
        or any(not isinstance(step, str) or not step for step in value["after_steps"])
        or len(set(value["after_steps"])) != len(value["after_steps"])
        or not set(value["after_steps"]) <= {row["id"] for row in selected["steps"]}
        or any(
            type(value[k]) is not int or value[k] <= 0
            for k in ("source_map_id", "source_id", "destination_id")
        )
        or not value["evidence"]
    ):
        raise ValueError("Malformed owned step return declaration")
    defeated = value.get("defeat_room_orders", [])
    if (
        not isinstance(defeated, list)
        or any(type(order) is not int or order <= 0 for order in defeated)
        or len(set(defeated)) != len(defeated)
    ):
        raise ValueError("Owned step return lacks exact failed room identities")
    if not set(defeated) <= {
        step["reference"]
        for step in selected["steps"]
        if step["kind"] == "room_victory"
    }:
        raise ValueError("Owned step return names an undeclared encounter")
    loss_events = value.get("loss_events", {})
    if not isinstance(loss_events, dict) or not set(loss_events) <= {
        str(order) for order in defeated
    }:
        raise ValueError("Owned loss feedback lacks its actual room")
    if loss_events:
        from wakfu_server import owned_story_mechanics

        pin = selected["native_sources"]
        native = owned_story_mechanics._sources(pin["path"], pin["sha256"])
        for event in loss_events.values():
            if (
                not isinstance(event, dict)
                or set(event) != {"scenario", "event"}
                or native["map_id"] != selected["map_id"]
                or any(type(event[k]) is not int or event[k] <= 0 for k in event)
                or event["scenario"]
                != owned_story_mechanics.event_scenario(native, event["event"])
            ):
                raise ValueError(
                    "Owned loss feedback differs from installed native Lua"
                )
    from wakfu_server import generic_transports
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_runtime_config import canonical_hash

    source = generic_transports.source(value["source_map_id"], value["source_id"])
    choices = (
        []
        if source is None
        else [
            row
            for row in source["destinations"]
            if row["destination_id"] == value["destination_id"]
        ]
    )
    if (
        source is None
        or canonical_hash(source) != value["source_sha256"]
        or len(choices) != 1
    ):
        raise ValueError("Owned step return lost its exact original source")
    target = choices[0]
    # A declared step may use the actual private map's literal free exit,
    # as well as the established public self-map fallback. Both routes still
    # require the original source pin and a real durable completion receipt.
    private_exit = value["source_map_id"] == selected["map_id"]
    if (
        (not private_exit and target["map_id"] != value["source_map_id"])
        or target["map_id"] == selected["map_id"]
        or target["criterion"]
        or target["cyZ"] >= 0
        or target["cyX"]
        or target["cyW"]
        or target["native_altitude_walkable"] is not True
        or tuple(target[k] for k in ("x", "y", "z"))
        not in published_geometry(target["map_id"]).cells
    ):
        raise ValueError("Owned step return is not a literal free public fallback")
    return {k: target[k] for k in ("map_id", "x", "y", "z")}


def policy(selected):
    value = selected.get("terminal_returns")
    if value is None:
        return None
    if isinstance(value, dict) and value.get("schema") == STEP_SCHEMA:
        _step_destination(selected, value)
        return value
    if (
        not isinstance(value, dict)
        or set(value) != {"schema", "room_order", "victory", "defeat", "evidence"}
        or value["schema"] != SCHEMA
        or type(value["room_order"]) is not int
        or value["room_order"] <= 0
        or not value["evidence"]
        or value["defeat"] != {"kind": "recorded_entry"}
    ):
        raise ValueError("Malformed owned terminal return declaration")
    target = value["victory"]
    if target == {"kind": "recorded_entry"}:
        return value
    if (
        not isinstance(target, dict)
        or set(target) != {"source_map_id", "source_id", "source_sha256", "position"}
        or any(
            type(target[k]) is not int or target[k] <= 0
            for k in ("source_map_id", "source_id")
        )
        or not isinstance(target["position"], list)
        or len(target["position"]) != 3
        or any(type(v) is not int for v in target["position"])
    ):
        raise ValueError("Malformed owned terminal exterior source")
    from wakfu_server import generic_transports
    from wakfu_server.combat_geometry import published_geometry
    from wakfu_server.dungeon_runtime_config import canonical_hash

    source = generic_transports.source(target["source_map_id"], target["source_id"])
    if (
        source is None
        or canonical_hash(source) != target["source_sha256"]
        or target["position"]
        not in [
            [p[k] for k in ("x", "y", "z")]
            for p in source.get("approach_positions", ())
        ]
        or tuple(target["position"])
        not in published_geometry(target["source_map_id"]).cells
    ):
        raise ValueError("Owned terminal return lost its native exterior approach")
    return value


def _key(instance_id, fight_id):
    return f"owned-story-terminal-return:{instance_id}:{fight_id}"


def stage(db, store, fight, participants, original_monsters):
    """Called inside genuine combat settlement, including defeated participants."""
    from wakfu_server import dungeon_runtime, owned_story_controller as controller

    original_monsters = tuple(original_monsters)
    packets_by_owner = {}
    if not original_monsters or not original_monsters[0].get("instance_id", 0):
        return packets_by_owner
    for participant in participants:
        character_id, account_id = (
            participant["character_id"],
            participant["account_id"],
        )
        location = db.execute(
            "SELECT map_id,instance_id FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if location is None or not controller.recognizes_instance(
            db, location["instance_id"]
        ):
            continue
        _, configuration = dungeon_runtime.configuration_for_instance(
            db, location["instance_id"]
        )
        selected = controller.policy(configuration)
        declaration = policy(selected)
        if declaration is None:
            continue
        character = store.character(account_id, character_id, db)
        controller._scope(db, store, character, check_position=False)
        row = db.execute(
            "SELECT e.*,f.status AS fight_status,p.team "
            "FROM dungeon_room_encounters e JOIN combat_fights f ON f.id=e.fight_id "
            "JOIN combat_fight_participants p ON p.fight_id=e.fight_id "
            "WHERE e.fight_id=%s AND e.instance_id=%s AND p.character_id=%s AND p.account_id=%s",
            (fight.id, character["instance_id"], character_id, account_id),
        ).fetchone()
        if declaration["schema"] == STEP_SCHEMA:
            if (
                row is None
                or row["room_order"] not in declaration.get("defeat_room_orders", ())
                or row["player_team"] == fight.winner
            ):
                continue
            declared_order = row["room_order"]
        else:
            declared_order = declaration["room_order"]
        if (
            fight.phase != "finished"
            or type(fight.winner) is not int
            or fight.winner not in (0, 1)
            or row is None
            or row["fight_status"] != "finished"
            or row["encounter_scope"] != "main"
            or row["room_order"] != declared_order
            or row["team"] != row["player_team"]
            or character_id not in fight.actors
            or fight.actors[character_id].team != row["player_team"]
        ):
            raise ValueError("Owned terminal return lacks a genuine settled encounter")
        victory = row["player_team"] == fight.winner
        if (
            row["status"] != ("victory" if victory else "defeat")
            or row["result"].get("victory") is not victory
        ):
            raise ValueError("Owned terminal return contradicts settled result")
        spawned = db.execute(
            "SELECT g.members,r.asset_map_id FROM dungeon_room_spawn_receipts r "
            "JOIN combat_groups g ON g.instance_id=r.instance_id AND g.map_id=r.asset_map_id AND g.group_id=r.group_id "
            "WHERE r.instance_id=%s AND r.room_order=%s",
            (character["instance_id"], row["room_order"]),
        ).fetchone()
        expected = next(
            (
                room
                for room in configuration["compiled_plan"]["rooms"]
                if room["order"] == row["room_order"]
            ),
            None,
        )
        original = tuple(original_monsters)
        identities = {(m["id"], m["ref"]) for m in original}
        if (
            spawned is None
            or spawned["asset_map_id"] != selected["map_id"]
            or expected is None
            or len(identities) != len(original)
            or not identities
            or identities != {(m["id"], m["ref"]) for m in spawned["members"]}
            or Counter(m["ref"] for m in original)
            != Counter(
                {
                    m["ref_id"]: sum(
                        n["count"]
                        for n in expected["monsters"]
                        if n["ref_id"] == m["ref_id"]
                    )
                    for m in expected["monsters"]
                }
            )
            or any(
                m["id"] not in fight.actors
                or fight.actors[m["id"]].controlled
                or fight.actors[m["id"]].team == row["player_team"]
                for m in original
            )
        ):
            raise ValueError(
                "Owned terminal return differs from original native formation"
            )
        from wakfu_server.combat_scene_box_goals import qualified_result

        board_victory = qualified_result(fight, original) if victory else False
        from wakfu_server.combat_scene_ball_goals import qualified_result as ball_result

        ball_victory = ball_result(fight, original) if victory else False
        if (
            victory
            and (getattr(fight, "native_encounter_scene", None) or {})
            .get("descriptor", {})
            .get("ball_goals")
            is not None
            and not ball_victory
        ):
            raise ValueError("Owned ball victory lacks its native touchdown")
        board_victory = board_victory or ball_victory
        if (
            victory
            and (getattr(fight, "native_encounter_scene", None) or {})
            .get("descriptor", {})
            .get("native_movement_escape")
            is not None
        ):
            from wakfu_server.combat_scene_movement_escape import outcome_qualified

            if not outcome_qualified(fight):
                raise ValueError(
                    "Owned escape victory lacks its committed native departure"
                )
            board_victory = True
        from wakfu_server.combat_test_commands import administrative_victory

        operator_victory = victory and administrative_victory(
            fight, account_id=character["account_id"], character_id=character["id"]
        )
        if (
            victory
            and not board_victory
            and (
                (
                    not {m["id"] for m in original}
                    <= {
                        e.get("actor_id")
                        for e in fight.events
                        if e.get("kind") == "death"
                    }
                    and not operator_victory
                )
                or any(fight.actors[m["id"]].hp > 0 for m in original)
            )
        ):
            raise ValueError("Owned terminal victory lacks original native deaths")
        storage.record_event(
            db,
            character_id,
            _key(character["instance_id"], fight.id),
            dict(
                kind=SCHEMA,
                instance_id=character["instance_id"],
                fight_id=fight.id,
                profile_sha256=controller._digest(selected),
                victory=victory,
                original_actor_ids=sorted(m["id"] for m in original),
            ),
        )
        actor = fight.actors[character_id]
        from wakfu_server import owned_story_defeat_qualification

        if (
            not victory
            and actor.hp <= 0
            and not participant.get("withdrawn", False)
            and not getattr(actor, "pve_withdrawn", False)
            and any(
                event.get("kind") == "death" and event.get("actor_id") == character_id
                for event in fight.events
            )
            and owned_story_defeat_qualification.qualified(
                selected, fight, character_id, original, row["room_order"]
            )
        ):
            from wakfu_server.achievements import mission_toolkit
            from wakfu_server import owned_story_mechanics

            if any(
                step["kind"] == "room_defeat" and step["reference"] == row["room_order"]
                for step in selected["steps"]
            ):
                completed = controller._scope(
                    db, store, character, check_position=False
                )[1]
                step = controller.plan(
                    selected, completed, kind="room_defeat", reference=row["room_order"]
                )
                objectives = (
                    []
                    if step is None
                    else [
                        effect
                        for effect in step["effects"]
                        if effect["kind"] == "quest_objective"
                    ]
                )
                state = storage.load_locked(db, character_id) if objectives else None
                available = not objectives or any(
                    effect["quest_id"] in state["running"]
                    and effect["quest_id"] not in state["completed"]
                    and effect["objective_id"] not in state["objectives"]
                    for effect in objectives
                )
                if step is not None and available:
                    outcome = controller._settle(
                        db,
                        store,
                        character,
                        selected,
                        completed,
                        kind="room_defeat",
                        reference=row["room_order"],
                        evidence=dict(
                            fight_id=fight.id,
                            original_actor_ids=sorted(m["id"] for m in original),
                        ),
                        apply_effects=owned_story_mechanics.executor(selected),
                    )
                    packets_by_owner.setdefault(account_id, []).extend(
                        outcome["packets"]
                    )
            packets_by_owner.setdefault(account_id, []).extend(
                mission_toolkit.settle(
                    db,
                    store,
                    character,
                    f"owned-room-defeat:{character['instance_id']}:{fight.id}",
                    "owned_room_defeat",
                    row["room_order"],
                )
            )
    return packets_by_owner


def pending(db, store, character):
    from wakfu_server import owned_story_controller as controller

    if not controller.recognizes_instance(db, character.get("instance_id")):
        return None
    selected, completed = controller._scope(db, store, character, check_position=False)
    declaration = policy(selected)
    if declaration is None:
        return None
    if declaration["schema"] == STEP_SCHEMA:
        steps_complete = set(declaration["after_steps"]) <= completed
        if (
            not steps_complete
            and _step_failure(db, character, selected, declaration) is None
        ):
            return None
        if declaration["source_map_id"] == selected["map_id"]:
            if steps_complete:
                return _step_destination(selected, declaration)
            run = db.execute(
                "SELECT * FROM dungeon_instances WHERE instance_id=%s",
                (character["instance_id"],),
            ).fetchone()
            from wakfu_server.dungeon_recovery import _recorded_exterior

            destination = (
                None
                if run is None
                else _recorded_exterior(db, character["account_id"], run)
            )
            if destination is None:
                raise ValueError(
                    "Owned failed step return lacks its original public entry"
                )
            return destination
        run = db.execute(
            "SELECT entry_map_id,entry_object_id FROM dungeon_instances WHERE instance_id=%s",
            (character["instance_id"],),
        ).fetchone()
        if run is None or (run["entry_map_id"], run["entry_object_id"]) != (
            declaration["source_map_id"],
            declaration["source_id"],
        ):
            raise ValueError("Owned step return differs from its actual entrance")
        return _step_destination(selected, declaration)
    row = db.execute(
        "SELECT e.payload FROM character_achievement_events e JOIN dungeon_room_encounters r "
        "ON e.event_key='owned-story-terminal-return:' || r.instance_id::text || ':' || r.fight_id::text "
        "WHERE e.character_id=%s AND r.instance_id=%s AND r.room_order=%s "
        "AND r.status IN ('victory','defeat') ORDER BY r.fight_id DESC LIMIT 1",
        (character["id"], character["instance_id"], declaration["room_order"]),
    ).fetchone()
    if row is None:
        return None
    proof = row["payload"]
    if (
        proof.get("kind") != SCHEMA
        or proof.get("instance_id") != character["instance_id"]
        or proof.get("profile_sha256") != controller._digest(selected)
        or type(proof.get("victory")) is not bool
    ):
        raise ValueError("Owned terminal return receipt changed")
    if proof["victory"] and declaration["victory"] != {"kind": "recorded_entry"}:
        target = declaration["victory"]
        return dict(
            map_id=target["source_map_id"],
            **dict(zip(("x", "y", "z"), target["position"])),
        )
    run = db.execute(
        "SELECT * FROM dungeon_instances WHERE instance_id=%s",
        (character["instance_id"],),
    ).fetchone()
    from wakfu_server.dungeon_recovery import _recorded_exterior

    destination = _recorded_exterior(db, character["account_id"], run)
    if destination is None:
        raise ValueError("Owned terminal return lacks its original public entry")
    return destination


def _step_failure(db, character, selected, declaration):
    orders = declaration.get("defeat_room_orders", ())
    if not orders:
        return None
    row = db.execute(
        "SELECT e.payload,r.room_order FROM character_achievement_events e JOIN dungeon_room_encounters r "
        "ON e.event_key='owned-story-terminal-return:' || r.instance_id::text || ':' || r.fight_id::text "
        "WHERE e.character_id=%s AND r.instance_id=%s AND r.room_order=ANY(%s) "
        "AND r.status='defeat' ORDER BY r.fight_id DESC LIMIT 1",
        (character["id"], character["instance_id"], list(orders)),
    ).fetchone()
    if row is None:
        return None
    proof = row["payload"]
    from wakfu_server import owned_story_controller as controller

    if (
        proof.get("kind") != SCHEMA
        or proof.get("instance_id") != character["instance_id"]
        or proof.get("profile_sha256") != controller._digest(selected)
        or proof.get("victory") is not False
    ):
        raise ValueError("Owned failed step return lost its genuine terminal proof")
    return row


def poll(session):
    """Use normal exit cleanup and delivery only after the actual combat closes."""
    state, runtime = session.state, session.runtime
    if (
        state.character is None
        or not state.loaded
        or state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
        or not state.character.get("instance_id")
    ):
        return False
    with runtime.STORE.connection() as db:
        destination = pending(db, runtime.STORE, state.character)
        loss_packets = []
        if destination is not None:
            from wakfu_server import (
                owned_story_controller as controller,
                owned_story_mechanics,
            )

            selected, completed = controller._scope(
                db, runtime.STORE, state.character, check_position=False
            )
            declaration = policy(selected)
            if (
                declaration["schema"] == STEP_SCHEMA
                and not set(declaration["after_steps"]) <= completed
            ):
                failure = _step_failure(db, state.character, selected, declaration)
                event = (
                    None
                    if failure is None
                    else declaration.get("loss_events", {}).get(
                        str(failure["room_order"])
                    )
                )
                if event is not None:
                    loss_packets = [
                        owned_story_mechanics.scenario_packet(selected, event["event"])
                    ]
    if destination is None:
        return False
    from wakfu_server import dungeon_exit

    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=state.character["id"],
        )

        def destination_for(db, character, run):
            current = pending(db, runtime.STORE, character)
            if current is None:
                raise ValueError("Owned terminal return no longer owns this member")
            return current

        dungeon_exit._leave(
            runtime.STORE,
            state.account_id,
            state.generation,
            state.character["id"],
            in_fight=lambda identity: runtime.COMBAT_SESSIONS.lookup_character(identity)
            is not None,
            destination_for=destination_for,
        )
        runtime.POSITIONS.rebind_selected(
            state.account_id, state.generation, state.character["id"]
        )
    if loss_packets:
        runtime.send_batch(state.connection, state.service, loss_packets)
    session.deliver_dungeon_transitions(before_action=True)
    return True
