"""Native emotes at finite, actual actor-bound owned story positions."""

from wakfu_server import owned_story_controller as controller


def triggers(selected):
    rows = selected.get("emote_triggers", [])
    if not isinstance(rows, list):
        raise ValueError("Owned emote triggers must be explicit")
    seen = set()
    for row in rows:
        if (
            not isinstance(row, dict)
            or set(row) != {"reference", "actor_role", "positions", "evidence"}
            or type(row["reference"]) is not int
            or row["reference"] <= 0
            or row["reference"] in seen
            or not isinstance(row["actor_role"], str)
            or not row["actor_role"]
            or not row["evidence"]
            or not isinstance(row["positions"], list)
            or not row["positions"]
            or any(
                not isinstance(p, list)
                or len(p) != 3
                or any(type(v) is not int for v in p)
                for p in row["positions"]
            )
            or len(set(map(tuple, row["positions"]))) != len(row["positions"])
            or not any(
                step["kind"] == "emote_performed"
                and step["reference"] == row["reference"]
                for step in selected["steps"]
            )
        ):
            raise ValueError("Malformed source-scoped native emote trigger")
        seen.add(row["reference"])
    return rows


def performed(db, store, character, reference):
    """Caller has already authorized the actual native emote occupation."""
    if not controller.recognizes_instance(db, character.get("instance_id", 0)):
        return []
    selected, completed = controller._scope(db, store, character)
    rows = [row for row in triggers(selected) if row["reference"] == reference]
    if not rows:
        return []
    from wakfu_server import owned_story_admission, owned_story_mechanics
    from wakfu_server.combat_geometry import published_geometry

    row = rows[0]
    step = controller.plan(
        selected, completed, kind="emote_performed", reference=reference
    )
    if step is None:
        return []
    objectives = [
        effect for effect in step["effects"] if effect["kind"] == "quest_objective"
    ]
    if objectives:
        from wakfu_server.achievements import storage

        state = storage.load_locked(db, character["id"])
        if not any(
            effect["quest_id"] in state["running"]
            and effect["quest_id"] not in state["completed"]
            and effect["objective_id"] not in state["objectives"]
            for effect in objectives
        ):
            # A questless or already-earned visit must not consume the later
            # assigned character's one story exercise or native presentation.
            return []
    position = tuple(character[k] for k in ("x", "y", "z"))
    cells = published_geometry(selected["map_id"]).cells
    if any(tuple(p) not in cells for p in row["positions"]):
        raise ValueError("Owned emote trigger lost its original native floor")
    if position not in set(map(tuple, row["positions"])):
        return []
    actors = [
        actor
        for actor in owned_story_admission.scene_actor_rows(db, store, character)
        if actor["role"] == row["actor_role"]
    ]
    if len(actors) != 1:
        raise ValueError("Owned emote requires its actual scoped native actor")
    actor = actors[0]
    delta = {1: (1, 0), 3: (0, 1), 5: (-1, 0), 7: (0, -1)}.get(
        character.get("direction")
    )
    if delta is None or (
        character["x"] + delta[0],
        character["y"] + delta[1],
        character["z"],
    ) != (actor["x"], actor["y"], actor["z"]):
        return []
    result = controller._settle(
        db,
        store,
        character,
        selected,
        completed,
        kind="emote_performed",
        reference=reference,
        evidence=dict(
            emote_id=reference, actor_id=actor["actor_id"], position=list(position)
        ),
        apply_effects=owned_story_mechanics.executor(selected),
    )
    return result["packets"]


def validate_sources(selected, native, geometry):
    """Reject an invalid authored area before publishing the configuration."""
    for row in triggers(selected):
        actors = [
            a for a in native.get("scene_actors", ()) if a["role"] == row["actor_role"]
        ]
        if len(actors) != 1:
            raise ValueError("Owned emote area has no unique native actor")
        actor = actors[0]
        if tuple(actor["position"]) not in geometry.cells or any(
            tuple(p) not in geometry.cells
            or p[2] != actor["position"][2]
            or abs(p[0] - actor["position"][0]) + abs(p[1] - actor["position"][1]) != 1
            for p in row["positions"]
        ):
            raise ValueError("Owned emote area leaves adjacent original native floor")
