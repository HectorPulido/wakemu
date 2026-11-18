"""Resolve published NPC click targets before ordinary dialogue authorization.

This adapter supplies position and range only. The dialogue handlers still own
availability, quest criteria, ownership and all progression writes after arrival.
"""

from collections import deque

from wakfu_server import npc_dialogue, npc_world


def approach_cells(geometry, row):
    """Find nearby floors with a short native route into the NPC's approach.

    A Manhattan radius alone admits conversations through walls. Traverse the
    directed graph backwards so each accepted floor can actually approach the
    actor, without leaving its configured interaction range. Existing platform
    anchors take precedence over an inaccessible decorative actor surface.
    """
    from wakfu_server.npc_interaction_anchors import interaction_anchor

    anchor = interaction_anchor(row) or row
    center = tuple(anchor[axis] for axis in ("x", "y", "z"))

    def nearby(cell):
        return npc_world.nearby(dict(row, **dict(zip(("x", "y", "z"), cell))), row)

    if center in geometry.cells:
        seeds = {center}
    else:
        # Some native decorative actors occupy no walkable surface. Use their
        # actual floor column, or immediately adjacent floors, rather than
        # inventing a walkable actor cell or a connection across a wall.
        seeds = {
            (center[0], center[1], center[2] + dz) for dz in (-1, 0, 1)
        } & geometry.cells
        if not seeds:
            seeds = {
                (center[0] + dx, center[1] + dy, center[2] + dz)
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
                for dz in (-1, 0, 1)
            } & geometry.cells
    goals = {cell for cell in seeds if nearby(cell)}
    pending = deque((cell, 0) for cell in sorted(goals))
    while pending:
        cell, distance = pending.popleft()
        if distance >= row["interaction_range"]:
            continue
        for source in geometry.incoming.get(cell, ()):
            if source not in goals and nearby(source):
                goals.add(source)
                pending.append((source, distance + 1))
    return frozenset(goals)


def _same_scene(character, row):
    return (character["map_id"], character.get("instance_id", 0)) == (
        row["map_id"],
        row["instance_id"],
    )


def _matches(row, actor, action, request):
    from wakfu_server import rii_airyna_dialogue
    from wakfu_server.achievements import npc_dialogue_actions, rii_free_practice

    airyna = (
        row["actor_id"] == rii_airyna_dialogue.ACTOR
        and row["reference_id"] == 5460
        and (row["map_id"], row["instance_id"]) == (1388, 0)
    )
    if request is not None:
        if airyna and request == dict(
            speaker_type=2,
            speaker_id=rii_airyna_dialogue.ACTOR,
            node_id=rii_airyna_dialogue.ROOT,
        ):
            return True
        return npc_world.matches_open_request(row, request)
    return row["actor_id"] == actor and (
        action in row["action_ids"]
        or npc_dialogue_actions.resolve(row, action) is not None
        or airyna
        and action in (rii_airyna_dialogue.ACTION, rii_free_practice.ACTION)
    )


def _published_native_anchor(db, character, actor, action, request):
    """Reattest an existing provider before projecting its published approach."""
    from wakfu_server import quest_npc

    published = quest_npc.publication(db)
    if published is None:
        return None
    item = next(
        (
            item
            for item in published[0]["placements"]
            if item["row"]["actor_id"] == actor
            and any(
                field in item
                for field in ("existing_native_actor", "existing_dialogue_actor")
            )
        ),
        None,
    )
    if item is None or item.get("interaction_anchor") is None:
        return None
    qualified, item = quest_npc._row(db, actor, published)
    if _same_scene(character, qualified) and _matches(
        qualified, actor, action, request
    ):
        return dict(qualified, **item["interaction_anchor"])
    return None


def resolve(store, character, opcode, body):
    """Return an existing same-scene target for an initial NPC click, or None.

    Choice requests never initiate walking. Malformed packets remain the concern
    of the existing request handler and cannot select a movement destination.
    """
    if opcode == 13222 and len(body) == 16:
        actor, action = npc_world.decode_interaction(body)
        request = None
    elif opcode == npc_dialogue.OPEN_REQUEST and len(body) == 13:
        request = npc_dialogue.decode_request(opcode, body)
        actor, action = request["speaker_id"], None
    else:
        return None

    from wakfu_server import (
        modulox_npc,
        ruel_hunt_npc,
        ruel_investigation_npc,
        weekly_hunter_npc,
    )

    with store.connection() as db:
        # These actors are published by their providers rather than the generic
        # world_dialogue_npcs table. Keep their existing enablement authority.
        if actor == ruel_hunt_npc.ACTOR:
            row = ruel_hunt_npc.placement()
            if (
                _same_scene(character, row)
                and _matches(row, actor, action, request)
                and ruel_hunt_npc._enabled(db)
            ):
                return row
            return None
        if actor in ruel_investigation_npc.SUSPECTS:
            row = ruel_investigation_npc.placement(actor)
            if (
                _same_scene(character, row)
                and _matches(row, actor, action, request)
                and ruel_hunt_npc._enabled(db)
            ):
                from wakfu_server.achievements import storage

                state = storage.load_locked(db, character["id"])
                if 3973 in state["running"]:
                    return row
            return None
        if actor == modulox_npc.ACTOR:
            row = modulox_npc.row(character)
            if (
                _same_scene(character, row)
                and _matches(row, actor, action, request)
                and modulox_npc.enabled(db)
            ):
                return row
            return None
        if actor == weekly_hunter_npc.ACTOR and action == weekly_hunter_npc.ACTION:
            anchor = _published_native_anchor(db, character, actor, action, request)
            if anchor is not None:
                return anchor
            row = weekly_hunter_npc._actor(db)
            if _same_scene(character, row):
                return dict(row, interaction_range=4)
            return None

        rows = npc_world.load_scene(
            db, character["map_id"], character.get("instance_id", 0)
        )
        row = next((row for row in rows if _matches(row, actor, action, request)), None)
        if row is None:
            return None
        from wakfu_server import quest_npc

        if row.get("provenance", "").startswith(quest_npc.PREFIX):
            published = row.get("_quest_publication")
            if published is not None:
                item = next(
                    item
                    for item in published[0]["placements"]
                    if item["row"]["actor_id"] == row["actor_id"]
                )
                anchor = item.get("interaction_anchor")
                if anchor is not None:
                    return dict(row, **anchor)
        else:
            anchor = _published_native_anchor(db, character, actor, action, request)
            if anchor is not None:
                return anchor
        return row
