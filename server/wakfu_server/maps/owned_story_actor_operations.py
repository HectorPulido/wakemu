"""Native type-one actions on authenticated, owner-scoped story actors.

The immutable story source declares the original aMg action and its consumer.
This adapter grants neither combat control nor quest credit. Consumers retain
their own transactional occupation, item and objective settlement rules.
"""

from wakfu_server import owned_story_admission, owned_story_controller
from wakfu_server import owned_story_mechanics, npc_world, npc_placements


def native_actions(reference):
    """Read one indexed original breed, never the whole monster catalog."""
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    breed = native_catalog.record(
        DATA_ROOT / "monster-encyclopedia.json", "monsters", str(reference)
    )
    if not isinstance(breed, dict) or not isinstance(breed.get("world_actions"), list):
        raise ValueError("Missing original native actor world actions")
    return breed["world_actions"]


def allowed(db, store, character, operation):
    """Check the original native action criterion in the current owned context."""
    return owned_story_mechanics.allowed(
        db, store, character, operation["native_action"]["clT"]
    )


def declarations(selected):
    native = owned_story_mechanics.sources(selected)
    actors = {row["role"]: row for row in native.get("scene_actors", ())}
    rows = native.get("actor_operations", ())
    if not isinstance(rows, (list, tuple)):
        raise ValueError("Invalid native story actor operations")
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or not {"role", "action_id", "consumer", "native_action", "evidence"}
            <= set(row)
            or set(row)
            - {
                "role",
                "action_id",
                "consumer",
                "native_action",
                "evidence",
                "parameters",
            }
            or "parameters" in row
            and not isinstance(row["parameters"], dict)
            or row["role"] not in actors
            or type(row["action_id"]) is not int
            or row["action_id"] <= 0
            or row["consumer"] != "healing"
            or not isinstance(row["evidence"], str)
            or not row["evidence"].strip()
            or (row["role"], row["action_id"]) in seen
        ):
            raise ValueError("Story actor operation lacks its reviewed source")
        action = row["native_action"]
        if (
            not isinstance(action, dict)
            or action.get("native_class") != "aMg"
            or action.get("d") != row["action_id"]
            or action.get("aGJ") != 1
            or type(action.get("getDuration")) is not int
            or action["getDuration"] < 0
            or type(action.get("clx")) is not int
            or action["clx"] <= 0
            or type(action.get("clT")) is not str
        ):
            raise ValueError("Story actor operation differs from native type-one aMg")
        if action not in native_actions(actors[row["role"]]["reference"]):
            raise ValueError(
                "Story actor action differs from its original native breed"
            )
        seen.add((row["role"], row["action_id"]))
    return tuple(rows)


def spawn(row, *, character, selected):
    """Enable only declared original MRU actions; ordinary models stay inert."""
    operations = [
        item for item in declarations(selected) if item["role"] == row["role"]
    ]
    if not operations:
        return npc_placements.spawn_owned(row, character=character)
    # Reuse the render-only adapter's complete scope and wire-model checks
    # before enabling its separately source-qualified native action mask.
    npc_placements.spawn_owned(row, character=character)
    # The final native UID list is a blacklist, as in npc_world.spawn.
    # Each operation attests its original type-one action; consumers never
    # publish a made-up action or invert this list into an enable mask.
    enabled = {item["action_id"] for item in operations}
    disabled = [
        action["d"]
        for action in native_actions(row["reference_id"])
        if action["d"] not in enabled
    ]
    return npc_placements._spawn(dict(row, native_action_ids=disabled))


def _selection(db, store, character, identity, action_id):
    selected, _ = owned_story_controller._scope(db, store, character)
    actors = owned_story_admission.scene_actor_rows(db, store, character)
    matches = [
        (actor, operation)
        for actor in actors
        for operation in declarations(selected)
        if actor["actor_id"] == identity
        and actor["role"] == operation["role"]
        and operation["action_id"] == action_id
    ]
    if len(matches) > 1:
        raise ValueError("Ambiguous owner-scoped native actor action")
    return matches[0] if matches else None


def handle(session):
    state, runtime = session.state, session.runtime
    character = state.character
    if (
        state.opcode != 13222
        or character is None
        or not character.get("instance_id")
        or not isinstance(state.body, bytes)
        or len(state.body) != 16
    ):
        return False
    identity, action_id = npc_world.decode_interaction(state.body)
    with runtime.STORE.connection() as db:
        if not owned_story_controller.recognizes_instance(db, character["instance_id"]):
            return False
        selected = _selection(db, runtime.STORE, character, identity, action_id)
    if selected is None:
        return False
    if (
        not state.loaded
        or state.fight is not None
        or state.spectator_session is not None
        or state.environment_ticket is not None
        or session.environment_blocked()
    ):
        raise ValueError("Native actor operation requires a ready idle owner")
    with runtime.POSITIONS.account_barrier(state.account_id):
        runtime.flush_positions(
            account_id=state.account_id,
            generation=state.generation,
            character_id=character["id"],
        )
        with runtime.STORE.connection() as db:
            current = runtime.STORE.character(state.account_id, character["id"], db)
            if current is None:
                raise ValueError("Native actor operation lost its selected owner")
            selected = _selection(db, runtime.STORE, current, identity, action_id)
            if selected is not None and not allowed(
                db, runtime.STORE, current, selected[1]
            ):
                raise ValueError("Native actor action criterion is not satisfied")
        if selected is None:
            raise ValueError("Native actor operation left its owned scene")
        row, operation = selected
        from wakfu_server.combat_geometry import published_geometry
        from wakfu_server.npc_approach_target import approach_cells

        state.character = current
        row = dict(row, interaction_range=2)
        geometry = published_geometry(current["map_id"])
        goals = approach_cells(geometry, row)
        if session.approach_actor(goals.__contains__, geometry=geometry):
            return True
        if not npc_world.nearby(state.character, row):
            raise ValueError("Native actor operation is outside interaction range")
        from wakfu_server import owned_story_actor_healing as consumer

        consumer.begin(session, row, operation)
    return True
