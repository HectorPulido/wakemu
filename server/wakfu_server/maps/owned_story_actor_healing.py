"""Timed native healing actions on source-qualified owned story actors.

The native client starts its original aMg progress UI before sending13222.
The server independently waits the original duration and revalidates the same
lease, actor, source, location and running quest before ordinary settlement.
"""

from datetime import timedelta

from wakfu_server import owned_story_controller as controller


def validate(operation):
    action = operation.get("native_action", {})
    parameters = operation.get("parameters", {})
    if (
        operation.get("consumer") != "healing"
        or action.get("aGJ") != 1
        or action.get("clx") != 222
        or type(action.get("getDuration")) is not int
        or not 0 < action["getDuration"] <= 60000
        or set(parameters) != {"quest_id", "objective_id", "step_reference"}
        or any(type(value) is not int or value <= 0 for value in parameters.values())
        or parameters["step_reference"] != operation.get("action_id")
    ):
        raise ValueError("Healing lacks its exact native action and objective")
    return parameters


def _selection(db, store, character, actor, action):
    from wakfu_server import owned_story_actor_operations as operations

    selected = operations._selection(db, store, character, actor, action)
    if selected is None:
        raise ValueError("Healing actor left its authenticated owned scene")
    row, operation = selected
    parameters = validate(operation)
    from wakfu_server.achievements import storage
    from wakfu_server import owned_story_npcs, npc_world

    state = storage.load_locked(db, character["id"])
    if (
        parameters["quest_id"] not in state["running"]
        or parameters["quest_id"] in state["completed"]
        or not npc_world.nearby(character, dict(row, interaction_range=2))
        or not owned_story_npcs._criterion(
            store, character, state, operation["native_action"]["clT"]
        )
    ):
        raise ValueError(
            "Healing requires its running quest and original nearby action"
        )
    policy, completed = controller._scope(db, store, character)
    matching = [
        step
        for step in policy["steps"]
        if step["kind"] == "npc_spoken"
        and step["reference"] == parameters["step_reference"]
        and {
            "kind": "quest_objective",
            "quest_id": parameters["quest_id"],
            "objective_id": parameters["objective_id"],
        }
        in step["effects"]
    ]
    if len(matching) != 1 or not set(matching[0]["requires"]) <= completed:
        raise ValueError("Healing lacks its source-qualified ordinary controller step")
    return row, operation, policy, completed


def begin(session, row, operation):
    """Start one operation after the common actor dispatcher reached native floor."""
    from wakfu_server.paid_containers import _leased_owner

    state, runtime = session.state, session.runtime
    validate(operation)
    previous = getattr(state.connection, "owned_story_healing", None)
    now = runtime.STORE.now()
    with runtime.STORE.connection() as db:
        _leased_owner(
            runtime.STORE, db, state.account_id, state.generation, state.character
        )
        current = runtime.STORE.character(state.account_id, state.character["id"], db)
        actual, declaration, _, _ = _selection(
            db, runtime.STORE, current, row["actor_id"], operation["action_id"]
        )
        if declaration != operation or actual["source_sha256"] != row["source_sha256"]:
            raise ValueError("Healing source changed before occupation")
        identity = dict(
            account_id=state.account_id,
            generation=state.generation,
            character_id=current["id"],
            map_id=current["map_id"],
            instance_id=current["instance_id"],
            actor_id=actual["actor_id"],
            action_id=operation["action_id"],
            position=[current[k] for k in ("x", "y", "z")],
            source_sha256=actual["source_sha256"],
            operation_sha256=controller._digest(operation),
        )
        if previous is not None:
            if previous["identity"] == identity:
                return True
            raise ValueError("Another native healing occupation is active")
        state.connection.owned_story_healing = dict(
            identity=identity,
            due_at=now
            + timedelta(milliseconds=operation["native_action"]["getDuration"]),
        )
        state.character = current
    return True


def poll(session):
    """Finish on the ordinary session tick; movement/disconnect cannot grant credit."""
    from wakfu_server.paid_containers import _leased_owner

    state, runtime = session.state, session.runtime
    ticket = getattr(state.connection, "owned_story_healing", None)
    if ticket is None:
        return False
    identity = ticket["identity"]
    if (
        state.character is None
        or not state.loaded
        or state.fight is not None
        or state.combat_session is not None
        or state.spectator_session is not None
        or state.environment_ticket is not None
        or (state.account_id, state.generation, state.character["id"])
        != (identity["account_id"], identity["generation"], identity["character_id"])
    ):
        state.connection.owned_story_healing = None
        return False
    if (
        state.character["map_id"],
        state.character.get("instance_id", 0),
        [state.character[k] for k in ("x", "y", "z")],
    ) != (identity["map_id"], identity["instance_id"], identity["position"]):
        state.connection.owned_story_healing = None
        return False
    if runtime.STORE.now() < ticket["due_at"]:
        return False
    # Clear before attempting settlement. A changed source or canceled operation
    # is retryable through another real action, never an automatic future grant.
    state.connection.owned_story_healing = None
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=identity["character_id"],
        )
        with runtime.STORE.connection() as db:
            _leased_owner(
                runtime.STORE, db, state.account_id, state.generation, state.character
            )
            current = runtime.STORE.character(
                state.account_id, identity["character_id"], db
            )
            if (
                current["map_id"],
                current.get("instance_id", 0),
                [current[k] for k in ("x", "y", "z")],
            ) != (identity["map_id"], identity["instance_id"], identity["position"]):
                return False
            try:
                row, operation, policy, completed = _selection(
                    db,
                    runtime.STORE,
                    current,
                    identity["actor_id"],
                    identity["action_id"],
                )
            except ValueError:
                return False
            if (
                row["source_sha256"] != identity["source_sha256"]
                or controller._digest(operation) != identity["operation_sha256"]
            ):
                return False
            from wakfu_server import owned_story_mechanics

            result = controller._settle(
                db,
                runtime.STORE,
                current,
                policy,
                completed,
                kind="npc_spoken",
                reference=validate(operation)["step_reference"],
                evidence=dict(
                    native_actor=identity["actor_id"],
                    native_action=identity["action_id"],
                    duration_ms=operation["native_action"]["getDuration"],
                    source_sha256=identity["source_sha256"],
                ),
                apply_effects=owned_story_mechanics.executor(policy),
            )
            state.character = runtime.STORE.character(
                state.account_id, current["id"], db
            )
        session.publish_settled_quest_packets(result["packets"])
    return True
