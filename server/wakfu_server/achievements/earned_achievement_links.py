"""Settle native achievements earned by another authenticated story producer.

Bindings are explicit reconstructions. A journal flag alone is insufficient:
the source objective and its original owner-bound event must both be durable.
The existing reward outbox provides capacity retries and exactly-once delivery.
"""

from . import native_effective_eligibility

from copy import deepcopy

from . import storage, mission_dependencies

# Native5593 explicitly names the boss in5568's cat-house stage. It is an
# achievement (aqb=true), separate from the visible mission's own reward list.
BINDINGS = (
    dict(
        source_quest=5568,
        source_objective=11511,
        achievement_id=5591,
        objective_id=11541,
        room_order=1,
        route_key="legacy-map-312-18736-713",
        event_match=dict(kind="owned_cat_story_scene", event_id=23922),
    ),
    dict(
        source_quest=5568,
        source_objective=11513,
        achievement_id=5593,
        objective_id=11543,
        room_order=3,
        route_key="legacy-map-312-18736-713",
        event_match=dict(kind="owned_cat_story_scene", event_id=23926),
    ),
)


def plan(state, definition, objective_id, *, character, store, now_ms):
    """Advance an explicitly qualified native achievement without rewriting it."""
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    if (
        definition.get("native_class") != "aJM"
        or definition.get("aqb") is not True
        or any(definition.get(key) != 0 for key in ("cjU", "cjL", "getDuration"))
        or type(now_ms) is not int
        or now_ms < 0
    ):
        raise ValueError("Unqualified linked native achievement")
    identity = definition["d"]
    objectives = {row["d"]: row for row in definition["cjJ"]}
    if len(objectives) != len(definition["cjJ"]) or objective_id not in objectives:
        raise ValueError("Missing linked native achievement objective")
    candidate = deepcopy(state)
    if identity in candidate["completed"] or objective_id in candidate["objectives"]:
        return candidate, [], [], []
    objective = objectives[objective_id]
    if objective.get("ckf"):
        raise ValueError("Linked achievement requires a counter producer")
    authority = queries_from_state(candidate)
    for criterion in (
        native_effective_eligibility.criterion(definition),
        objective["ckc"],
        objective["cke"],
    ):
        if not dungeon_criteria.evaluate(
            store, criterion, character=character, queries=authority, now_ms=now_ms
        ):
            return candidate, [], [], []
    candidate["objectives"] = sorted(set(candidate["objectives"]) | {objective_id})
    if not set(objectives) <= set(candidate["objectives"]):
        candidate["running"] = sorted(set(candidate["running"]) | {identity})
        return candidate, [], [objective_id], []
    candidate["running"] = [
        value for value in candidate["running"] if value != identity
    ]
    candidate["completed"] = sorted(set(candidate["completed"]) | {identity})
    candidate["tracking"] = [
        value for value in candidate["tracking"] if value != identity
    ]
    candidate["completion_dates"][str(identity)] = now_ms
    candidate["recent"] = (candidate["recent"] + [dict(id=identity, date_ms=now_ms)])[
        -255:
    ]
    return (
        candidate,
        [(identity, deepcopy(row)) for row in definition["cjK"]],
        [objective_id],
        [identity],
    )


def settle(db, store, character, *, source_quest, source_objective, event_key):
    """Observe the source producer's persisted receipt inside its transaction."""
    from .service import _owner, drain_rewards

    _owner(db, character)
    bindings = [
        row
        for row in BINDINGS
        if (row["source_quest"], row["source_objective"])
        == (source_quest, source_objective)
    ]
    if not bindings:
        return []
    event = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (character["id"], event_key),
    ).fetchone()
    state = storage.load_locked(db, character["id"])
    if (
        event is None
        or not isinstance(event["payload"], dict)
        or event["payload"].get("owner") != character["id"]
        or type(event["payload"].get("fight_id")) is not int
        or event["payload"]["fight_id"] <= 0
        or source_objective not in state["objectives"]
        or source_quest not in set(state["running"]) | set(state["completed"])
    ):
        raise ValueError("Missing durable linked achievement source")
    packets = []
    for binding in bindings:
        if any(
            event["payload"].get(key) != value
            for key, value in binding["event_match"].items()
        ):
            raise ValueError("Linked achievement source event differs")
        victory = db.execute(
            "SELECT e.result FROM dungeon_room_encounters e "
            "JOIN dungeon_instances i ON i.instance_id=e.instance_id "
            "JOIN combat_fight_participants p ON p.fight_id=e.fight_id "
            "JOIN combat_fights f ON f.id=e.fight_id "
            "WHERE e.fight_id=%s AND e.instance_id=%s AND e.room_order=%s "
            "AND i.context_route_key=%s AND e.status='victory' AND f.status='finished' "
            "AND p.character_id=%s AND p.account_id=%s AND p.team=e.player_team",
            (
                event["payload"]["fight_id"],
                event["payload"].get("instance_id"),
                binding["room_order"],
                binding["route_key"],
                character["id"],
                character["account_id"],
            ),
        ).fetchone()
        if victory is None or victory["result"].get("victory") is not True:
            raise ValueError("Linked achievement lacks its original owned room victory")
        row = db.execute(
            "SELECT data FROM native_quest_metadata_definitions WHERE revision="
            "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
            "AND definition_id=%s",
            (binding["achievement_id"],),
        ).fetchone()
        if row is None:
            raise ValueError("Missing linked achievement native definition")
        before = storage.load_locked(db, character["id"])
        definition = row["data"]["native"]
        now_ms = int(store.now().timestamp() * 1000)
        planned = plan(
            before,
            definition,
            binding["objective_id"],
            character=character,
            store=store,
            now_ms=now_ms,
        )
        if not planned[2]:
            packets.extend(drain_rewards(db, store, character))
            continue
        result = mission_dependencies.settle(
            db,
            store,
            character,
            before,
            planned,
            {definition["d"]: definition},
            (),
            now_ms=now_ms,
        )
        packets.extend(result["packets"])
    return packets


def recover(db, store, character):
    """Recover omitted earned links from original victories, never journal alone.

    Selection may discard incremental packets because its absolute bootstrap
    follows. An operator can use the same hook for a targeted local repair.
    """
    state = storage.load_locked(db, character["id"])
    eligible = [
        row
        for row in BINDINGS
        if row["achievement_id"] not in state["completed"]
        and row["source_objective"] in state["objectives"]
        and row["source_quest"] in set(state["running"]) | set(state["completed"])
    ]
    if not eligible:
        return []
    packets = []
    events = db.execute(
        "SELECT v.event_key,v.payload FROM character_achievement_events v "
        "JOIN dungeon_room_encounters e ON e.fight_id::text=v.payload->>'fight_id' "
        "AND e.instance_id::text=v.payload->>'instance_id' "
        "JOIN dungeon_instances i ON i.instance_id=e.instance_id "
        "JOIN combat_fight_participants p ON p.fight_id=e.fight_id "
        "JOIN combat_fights f ON f.id=e.fight_id "
        "WHERE v.character_id=%s AND v.payload->>'owner'=%s "
        "AND v.payload->>'kind'='owned_cat_story_scene' "
        "AND v.payload->>'event_id'=ANY(%s) AND e.status='victory' "
        "AND f.status='finished' AND p.character_id=%s AND p.account_id=%s "
        "AND p.team=e.player_team AND e.result->>'victory'='true' "
        "ORDER BY v.event_key",
        (
            character["id"],
            str(character["id"]),
            [str(row["event_match"]["event_id"]) for row in eligible],
            character["id"],
            character["account_id"],
        ),
    ).fetchall()
    for event in events:
        for binding in eligible:
            if all(
                event["payload"].get(key) == value
                for key, value in binding["event_match"].items()
            ):
                packets.extend(
                    settle(
                        db,
                        store,
                        character,
                        source_quest=binding["source_quest"],
                        source_objective=binding["source_objective"],
                        event_key=event["event_key"],
                    )
                )
    return packets
