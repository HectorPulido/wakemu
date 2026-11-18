"""Resume an earned paid solo story run without resetting its native mechanics.

This is called only inside the existing owned-transfer transaction, after its
source departure and before normal target admission. The original instance,
pinned policy, room progress and controller receipts remain unchanged. Normal
`reused=True` admission retains its existing once-per-run native payment rule.
"""

from copy import deepcopy

from wakfu_server import dungeon_instances, dungeon_runtime_config, player_parties
from wakfu_server import owned_story_controller, owned_companion_rescue
from wakfu_server.achievements import storage


def paid_narrative(configuration):
    """Only the already declared roomless narrative context is persistent."""
    from wakfu_server.owned_noncombat_context import NARRATIVE

    return (
        configuration.get("topology", {}).get("policy") == NARRATIVE
        and configuration["topology"].get("rooms") == []
        and configuration.get("compiled_plan", {}).get("rooms") == []
    )


def _eligible(configuration, selected, state):
    if paid_narrative(configuration):
        return selected["admission"]["quest_id"] in set(state["running"]) | set(
            state["completed"]
        )
    return owned_companion_rescue.can_reenter(selected, state)


def compatible(previous, current):
    """An optional attachment cannot change already earned encounter mechanics."""
    old = owned_story_controller.policy(previous)
    new = owned_story_controller.policy(current)
    if old is None or new is None:
        return False
    old, new = deepcopy(old), deepcopy(new)
    old.pop("optional_companion", None)
    new.pop("optional_companion", None)
    if (
        old != new
        or previous["compiled_plan"]["rooms"] != current["compiled_plan"]["rooms"]
    ):
        return False
    if previous["topology"]["rooms"] != current["topology"]["rooms"]:
        return False
    for field in ("client_sha256", "topology_sha256"):
        if (
            previous["topology"]["exploration_geometry"][field]
            != current["topology"]["exploration_geometry"][field]
        ):
            return False
    return True


def prepare(db, store, account_id, generation, character_id, resolved, configuration):
    """Restore only a genuinely entered, completed and returned owner's run."""
    selected = owned_story_controller.policy(configuration)
    if selected is None:
        return None
    native = resolved["native_destination"]
    if native.get("cyW", 0) <= 0 or native.get("item_reference", 0) <= 0:
        return None
    player_parties._lock_members(db, [character_id])
    store.lock_character(db, account_id, generation, character_id)
    character = store.character(account_id, character_id, db)
    if (
        character["instance_id"] != 0
        or character["map_id"] != resolved["route"].entry_map_id
    ):
        raise ValueError("Paid story resumption lost its actual source position")
    state = storage.load_locked(db, character_id)
    if not _eligible(configuration, selected, state):
        return None
    route_key = dungeon_instances.canonical_context_key(resolved["route"])
    current_party = db.execute(
        "SELECT party_id FROM player_party_members WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    narrative = paid_narrative(configuration)
    room_join = "" if narrative else "JOIN dungeon_room_runs r USING(instance_id) "
    room_guard = (
        "AND NOT EXISTS (SELECT 1 FROM dungeon_room_runs r WHERE r.instance_id=i.instance_id) "
        if narrative
        else "AND r.status='completed' AND r.current_room=jsonb_array_length(r.rooms) "
    )
    run = db.execute(
        "SELECT i.*,p.leader_id,p.dungeon_solo,p.revision AS live_party_revision "
        "FROM dungeon_instances i "
        + room_join
        + "JOIN dungeon_instance_members m ON m.instance_id=i.instance_id AND m.character_id=%s "
        "JOIN player_parties p ON p.id=i.party_id "
        "WHERE i.created_by_character_id=%s AND i.context_route_key=%s "
        "AND i.status IN ('closed','completed') "
        + room_guard
        + "AND m.status='returned' ORDER BY i.instance_id DESC LIMIT 1 FOR UPDATE OF "
        + ("i,m,p" if narrative else "i,r,m,p"),
        (character_id, character_id, route_key),
    ).fetchone()
    if run is None:
        return None
    previous = dungeon_runtime_config.pinned_configuration(
        db, route_key, run["context_policy_version"]
    )
    prior_policy = owned_story_controller.policy(previous)
    if (
        not compatible(previous, configuration)
        or not _eligible(previous, prior_policy, state)
        or any(
            run[old] != getattr(resolved["route"], new)
            for old, new in (
                ("template_id", "template_id"),
                ("definition_id", "definition_id"),
                ("entry_map_id", "entry_map_id"),
                ("entry_object_id", "entry_object_id"),
                ("entry_destination_id", "destination_id"),
                ("start_map_id", "start_map_id"),
            )
        )
    ):
        return None
    members = db.execute(
        "SELECT character_id,status FROM dungeon_instance_members WHERE instance_id=%s ORDER BY character_id FOR UPDATE",
        (run["instance_id"],),
    ).fetchall()
    party_members = db.execute(
        "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY character_id",
        (run["party_id"],),
    ).fetchall()
    if members != [dict(character_id=character_id, status="returned")]:
        return None
    if current_party is not None:
        if (
            current_party["party_id"] != run["party_id"]
            or party_members != [dict(character_id=character_id)]
            or run["leader_id"] != character_id
        ):
            return None
    elif (
        run["dungeon_solo"] is not True or party_members or run["leader_id"] is not None
    ):
        return None
    admission = prior_policy["admission"]
    entry = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (
            character_id,
            f'owned-story-entry:{run["instance_id"]}:{admission["quest_id"]}',
        ),
    ).fetchone()
    # The original native admission and its entry-item debit committed in the
    # same `_enter` transaction. A map visit, completion flag or admin TP cannot
    # create this owner-bound entry receipt plus its actual route transition.
    if entry is None or any(
        entry["payload"].get(key) != value
        for key, value in dict(
            schema="owned-quest-instance-v1",
            quest_id=admission["quest_id"],
            objective_id=admission["objective_id"],
            instance_id=run["instance_id"],
            route_key=route_key,
        ).items()
    ):
        return None
    if narrative:
        visits = [
            step
            for step in prior_policy["steps"]
            if step["kind"] == "world_ready"
            and step["reference"] == prior_policy["map_id"]
            and not step["requires"]
        ]
        if not visits:
            return None
        for step in visits:
            visit = db.execute(
                "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
                (
                    character_id,
                    owned_story_controller._key(
                        prior_policy, run["instance_id"], step["id"]
                    ),
                ),
            ).fetchone()
            if visit is None or any(
                visit["payload"].get(key) != value
                for key, value in dict(
                    schema=owned_story_controller.SCHEMA,
                    profile_sha256=owned_story_controller._digest(prior_policy),
                    owner=character_id,
                    instance_id=run["instance_id"],
                    step=step["id"],
                ).items()
            ):
                return None
    witness = db.execute(
        "SELECT 1 FROM dungeon_transition_outbox WHERE instance_id=%s AND character_id=%s "
        "AND transition_kind='enter' AND source_map_id=%s AND destination_map_id=%s "
        "AND destination_instance_id=%s LIMIT 1",
        (
            run["instance_id"],
            character_id,
            run["entry_map_id"],
            run["start_map_id"],
            run["instance_id"],
        ),
    ).fetchone()
    busy = db.execute(
        "SELECT 1 FROM combat_fights f JOIN combat_fight_participants p ON p.fight_id=f.id "
        "WHERE p.character_id=%s AND f.status IN ('active','placement') LIMIT 1",
        (character_id,),
    ).fetchone()
    if witness is None or busy is not None:
        return None
    revision = run["live_party_revision"]
    if current_party is None:
        revision += 1
        db.execute(
            "UPDATE player_parties SET leader_id=%s,revision=%s WHERE id=%s",
            (character_id, revision, run["party_id"]),
        )
        db.execute(
            "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
            (character_id, run["party_id"]),
        )
    db.execute(
        "UPDATE dungeon_instances SET status='active',ended_at=NULL,party_revision=%s,revision=revision+1 WHERE instance_id=%s",
        (revision, run["instance_id"]),
    )
    db.execute(
        "UPDATE dungeon_instance_members SET session_generation=%s,party_revision=%s WHERE instance_id=%s AND character_id=%s",
        (generation, revision, run["instance_id"], character_id),
    )
    return run["instance_id"]
