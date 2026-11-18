"""Owner-only quest encounters bound to frozen native-map dungeon runs.

The same durable admission, native fight and exterior-return machinery serves
all declared profiles. A map visit, rat kill elsewhere, summon, surrender or
administrative result cannot stand in for the owned room's actual victory.
"""

from collections import Counter

from . import storage, mission_progress, mission_dependencies
from wakfu_server.quest_instance_configuration import (
    SCHEMA,
    reviewed_entry_gate,
    reviewed_reentry_quests,
    reviewed_pending_reentry,
)


def policy(configuration):
    value = configuration["topology"].get("owned_quest_encounter")
    if value is None:
        return None
    if (
        not isinstance(value, dict)
        or value.get("schema") != SCHEMA
        or value.get("maximum_members") != 1
        or type(value.get("maximum_members")) is not int
        or any(
            type(value.get(k)) is not int or value[k] <= 0
            for k in ("quest_id", "entry_objective", "victory_objective")
        )
        or not value.get("provenance")
        or not isinstance(value.get("roster"), list)
        or not value["roster"]
        or any(
            not isinstance(r, dict)
            or set(r) != {"reference", "count"}
            or any(
                type(r.get(k)) is not int or r[k] <= 0 for k in ("reference", "count")
            )
            for r in value["roster"]
        )
    ):
        raise ValueError("Invalid reviewed owned quest encounter policy")
    reviewed_reentry_quests(value)
    reviewed_pending_reentry(value)
    return value


def admission_phase(selected, state):
    """Separate optional mission callbacks from access to owned physical content."""
    quest = selected["quest_id"]
    if quest not in state["running"] or quest in state["completed"]:
        return "content_only"
    from wakfu_server.dungeon_achievement_authority import queries_from_state

    try:
        running = queries_from_state(state)["IsAchievementRunning"](quest)
    except ValueError:
        # Missing period authority cannot grant mission progress. It does not
        # prevent an otherwise authenticated physical visit or ordinary loot.
        return "content_only"
    return "running" if running else "content_only"


def initialize(db, session, resolved, *, store):
    """Fence the entire transition transaction before it commits any movement."""
    from wakfu_server import companions, dungeon_runtime_config, dungeon_instances

    route_key = dungeon_instances.canonical_context_key(resolved["route"])
    declared = db.execute(
        "SELECT configuration->'topology'->'owned_quest_encounter' AS policy "
        "FROM dungeon_runtime_configurations WHERE route_key=%s AND policy_version=%s",
        (route_key, session["context_policy_version"]),
    ).fetchone()
    if declared is None or declared["policy"] is None:
        return
    configuration = dungeon_runtime_config.pinned_configuration(
        db, route_key, session["context_policy_version"]
    )
    selected = policy(configuration)
    if selected is None:
        return
    members = list(session["members"])
    if len(members) != 1 or companions.controlled_count(db, members):
        raise ValueError("This quest instance requires one character without a company")
    owner = members[0]
    state = storage.load_locked(db, owner)
    phase = admission_phase(selected, state)
    if not reviewed_entry_gate(
        configuration["route"]["criterion"], selected["quest_id"], selected
    ):
        raise ValueError("Quest encounter lost its strict native admission criterion")
    target = db.execute(
        "SELECT c.id,c.account_id FROM characters c JOIN dungeon_instance_members m "
        "ON m.character_id=c.id AND m.instance_id=c.instance_id "
        "WHERE c.id=%s AND c.instance_id=%s AND c.map_id=%s AND m.status='active'",
        (owner, session["instance_id"], configuration["route"]["start_map_id"]),
    ).fetchone()
    if target is None:
        raise ValueError(
            "Quest admission lacks its actual owned destination membership"
        )
    character = store.character(target["account_id"], owner, db)
    if phase == "content_only":
        # Physical visits do not assign a mission or replay completed progress.
        # Native combat, loot and exit retain the same owned instance scope.
        session["owned_quest_encounter"] = dict(
            owner=owner, quest_id=selected["quest_id"], content_only=True
        )
        return
    # The enclosing transition hydrates the full native journal from this
    # committed state; an initialization failure rolls entry and progress back.
    _advance(
        db,
        store,
        character,
        selected,
        selected["entry_objective"],
        f'owned-quest-entry:{session["instance_id"]}:{selected["quest_id"]}',
        dict(instance_id=session["instance_id"], route_key=route_key),
    )
    session["owned_quest_encounter"] = dict(owner=owner, quest_id=selected["quest_id"])


def _advance(db, store, character, selected, objective, key, evidence):
    before = storage.load_locked(db, character["id"])
    if objective in before["objectives"]:
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) AND definition_id=%s",
        (selected["quest_id"],),
    ).fetchone()
    if row is None:
        raise ValueError("Owned quest encounter native definition is missing")
    definition = row["data"]["native"]
    now_ms = int(store.now().timestamp() * 1000)
    planned = mission_progress.advance_objective(
        before, definition, objective, character=character, store=store, now_ms=now_ms
    )
    if not storage.record_event(
        db,
        character["id"],
        key,
        dict(
            evidence,
            schema=SCHEMA,
            quest_id=selected["quest_id"],
            objective_id=objective,
        ),
    ):
        raise ValueError("Owned quest receipt conflicts with its uncompleted objective")
    result = mission_dependencies.settle(
        db,
        store,
        character,
        before,
        planned,
        {selected["quest_id"]: definition},
        (),
        now_ms=now_ms,
    )
    return list(result["packets"])


def qualified_roster(fight, original_monsters, selected):
    """Require original, fully defeated enemies with the frozen native species."""
    wanted = Counter()
    for row in selected["roster"]:
        wanted[row["reference"]] += row["count"]
    actual = Counter()
    identities = set()
    summons = getattr(fight, "native_summon_registrations", {})
    for monster in original_monsters:
        identity, reference = monster["id"], monster["ref"]
        actor = fight.actors.get(identity)
        if (
            identity in identities
            or identity in summons
            or actor is None
            or actor.hp > 0
            or actor.team == fight.winner
            or actor.controlled
        ):
            return False
        identities.add(identity)
        actual[reference] += 1
    return actual == wanted


def settle(db, store, character, fight, original_monsters):
    """Run after normal group settlement, inside the same reward transaction."""
    if (
        fight.phase != "finished"
        or type(fight.winner) is not int
        or fight.winner not in (0, 1)
        or type(character.get("instance_id")) is not int
        or character["instance_id"] <= 0
    ):
        return []
    encounter = db.execute(
        "SELECT e.*,i.context_route_key,i.context_policy_version,i.start_map_id AS asset_map_id FROM dungeon_room_encounters e "
        "JOIN dungeon_instances i USING(instance_id) WHERE e.fight_id=%s",
        (fight.id,),
    ).fetchone()
    if encounter is None:
        return []
    from wakfu_server import dungeon_runtime_config

    configuration = dungeon_runtime_config.pinned_configuration(
        db, encounter["context_route_key"], encounter["context_policy_version"]
    )
    selected = policy(configuration)
    if selected is None:
        return []
    if (
        encounter["status"] != "victory"
        or encounter["player_team"] != fight.winner
        or encounter.get("encounter_scope", "main") != "main"
        or encounter["result"].get("victory") is not True
        or encounter["result"].get("completed") is not True
        or encounter["room_order"] != 1
        or encounter["asset_map_id"] != configuration["route"]["start_map_id"]
        or character["map_id"] != encounter["asset_map_id"]
        or character["instance_id"] != encounter["instance_id"]
    ):
        return []
    members = db.execute(
        "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active' ORDER BY character_id",
        (encounter["instance_id"],),
    ).fetchall()
    participant = db.execute(
        "SELECT 1 FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s AND account_id=%s AND team=%s",
        (fight.id, character["id"], character["account_id"], fight.winner),
    ).fetchone()
    if members != [{"character_id": character["id"]}] or participant is None:
        return []
    spawned = db.execute(
        "SELECT g.members,g.status,r.asset_map_id FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
        "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
        "WHERE r.instance_id=%s AND r.room_order=1",
        (encounter["instance_id"],),
    ).fetchone()
    originals = [(row["id"], row["ref"]) for row in original_monsters]
    if (
        spawned is None
        or spawned["status"] != "defeated"
        or spawned["asset_map_id"] != encounter["asset_map_id"]
        or sorted((row["id"], row["ref"]) for row in spawned["members"])
        != sorted(originals)
    ):
        raise ValueError("Owned quest victory lacks its original durable group")
    if not qualified_roster(fight, original_monsters, selected):
        raise ValueError(
            "Owned quest victory differs from its frozen original formation"
        )
    before = storage.load_locked(db, character["id"])
    if admission_phase(selected, before) != "running":
        return []
    if selected["entry_objective"] not in before["objectives"]:
        # A mission assigned after entering has no authenticated entry credit.
        # Skip its callback without rolling back the real fight's normal loot.
        return []
    if selected["victory_objective"] in before["objectives"]:
        return []
    key = f'owned-quest-victory:{encounter["instance_id"]}:{fight.id}:{selected["quest_id"]}'
    return _advance(
        db,
        store,
        character,
        selected,
        selected["victory_objective"],
        key,
        dict(
            instance_id=encounter["instance_id"],
            fight_id=fight.id,
            route_key=encounter["context_route_key"],
        ),
    )
