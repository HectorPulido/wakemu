"""Settle certified native terminal checkpoints before startup aborts lost fights.

Only declared owner-only quest instances are supported. This is accounting from
an already earned outcome, never native combat replay, HP edits or forced wins.
Already-aborted incidents additionally require an explicitly reviewed digest.
"""

from copy import deepcopy
from types import SimpleNamespace
import logging


from . import storage, owned_quest_encounters

POLICY = "owned-quest-certified-terminal-v1"


def projection(raw, *, fight_id, owner, monsters, player_team):
    if (
        type(raw) is not dict
        or raw.get("id") != fight_id
        or raw.get("phase") != "finished"
        or type(raw.get("winner")) is not int
        or raw["winner"] != player_team
        or raw.get("checkpoint_schema") is not None
        or raw.get("rift_wave_state") is not None
        or raw.get("native_summon_registrations")
        or raw.get("native_companion_sources")
        or not isinstance(raw.get("actors"), dict)
    ):
        raise ValueError("Missing supported natural terminal checkpoint")
    original_ids = {row["id"] for row in monsters}
    if set(raw["actors"]) != {str(owner["character_id"]), *map(str, original_ids)}:
        raise ValueError("Terminal checkpoint differs from the original owned roster")
    events = raw.get("events", ())
    if not isinstance(events, (list, tuple)) or any(
        type(event) is not dict for event in events
    ):
        raise ValueError("Invalid certified terminal event history")
    actors = {}
    for key, source in raw["actors"].items():
        if type(source) is not dict:
            raise ValueError("Invalid certified terminal actor payload")
        value = deepcopy(source)
        identity = int(key)
        if (
            value.get("id") != identity
            or type(value.get("hp")) is not int
            or type(value.get("max_hp")) is not int
            or not 0 <= value["hp"] <= value["max_hp"]
            or type(value.get("controlled")) is not bool
            or type(value.get("team")) is not int
        ):
            raise ValueError("Invalid certified terminal actor")
        if identity == owner["character_id"]:
            if (
                not value["controlled"]
                or value.get("owner_id") != owner["account_id"]
                or value["team"] != player_team
                or value["hp"] <= 0
            ):
                raise ValueError("Terminal checkpoint has no living original winner")
        elif value["controlled"] or value["team"] == player_team or value["hp"] != 0:
            raise ValueError(
                "Terminal checkpoint contains an undefeated original enemy"
            )
        for field in (
            "effect_stats",
            "effect_maxima",
            "effect_minima",
            "effect_base_maxima",
            "effect_base_minima",
            "effect_percentages",
            "effect_resource_raw_currents",
        ):
            mapping = value.get(field)
            if mapping is not None:
                if type(mapping) is not dict:
                    raise ValueError("Invalid certified terminal effect mapping")
                value[field] = {int(k): v for k, v in mapping.items()}
        if value.get("position") is not None:
            if (
                not isinstance(value["position"], (list, tuple))
                or len(value["position"]) != 3
                or any(type(component) is not int for component in value["position"])
            ):
                raise ValueError("Invalid certified terminal actor position")
            value["position"] = tuple(value["position"])
        if value.get("effect_frozen") is not None:
            if not isinstance(
                value["effect_frozen"], (list, tuple, set, frozenset)
            ) or any(
                type(reference) is not int for reference in value["effect_frozen"]
            ):
                raise ValueError("Invalid certified terminal frozen effects")
            value["effect_frozen"] = frozenset(value["effect_frozen"])
        ledger = value.get("state_ledger")
        if ledger is not None:
            if (
                type(ledger) is not dict
                or not isinstance(ledger.get("entries", ()), (list, tuple))
                or any(type(row) is not dict for row in ledger.get("entries", ()))
            ):
                raise ValueError("Invalid certified terminal state ledger")
            value["state_ledger"] = SimpleNamespace(
                entries=tuple(
                    SimpleNamespace(**row) for row in ledger.get("entries", ())
                )
            )
        actors[identity] = SimpleNamespace(**value)
    terminal = [
        event for event in raw.get("events", ()) if event.get("kind") == "finished"
    ]
    deaths = {
        event.get("actor_id")
        for event in raw.get("events", ())
        if event.get("kind") == "death"
    }
    if (
        not terminal
        or terminal[-1].get("winner") != player_team
        or not original_ids <= deaths
    ):
        raise ValueError(
            "Terminal checkpoint lacks its actual enemy deaths and outcome"
        )
    fight = SimpleNamespace(**deepcopy(raw))
    fight.actors = actors
    return fight


def reviewed_roster(configuration, room_order):
    """Select the exact frozen room formation of a declared owned controller."""
    if type(room_order) is not int or room_order <= 0:
        raise ValueError("Invalid certified terminal room order")
    selected = owned_quest_encounters.policy(configuration)
    if selected is not None:
        if room_order != 1:
            raise ValueError("Single-room quest recovery cannot certify another room")
        return selected
    from wakfu_server import owned_story_controller

    selected = owned_story_controller.policy(configuration)
    if (
        selected is None
        or selected["map_id"] != configuration["route"]["start_map_id"]
        or not any(
            step["kind"] == "room_victory" and step["reference"] == room_order
            for step in selected["steps"]
        )
    ):
        raise ValueError("Story recovery has no reviewed room-victory producer")
    rooms = [
        room
        for room in configuration["compiled_plan"]["rooms"]
        if room["order"] == room_order
    ]
    if len(rooms) != 1 or not rooms[0].get("monsters"):
        raise ValueError("Story recovery lost its unique frozen room formation")
    roster = []
    for monster in rooms[0]["monsters"]:
        if any(
            type(monster.get(k)) is not int or monster[k] <= 0
            for k in ("ref_id", "count")
        ):
            raise ValueError("Story recovery has an invalid original species roster")
        roster.append(dict(reference=monster["ref_id"], count=monster["count"]))
    return dict(roster=roster)


def recover(store, db, fight_id, *, reviewed_aborted_sha256=None):
    """Recover one certified outcome atomically, or leave all state unchanged."""
    from wakfu_server import dungeon_runtime_config, dungeon_progression
    from wakfu_server.fight_checkpoint_store import checkpoint_digest

    candidate = db.execute(
        "SELECT f.status AS fight_status,f.fight_kind,c.status AS checkpoint_status,c.revision,c.snapshot,"
        "e.instance_id,e.room_order,e.status AS encounter_status,e.encounter_scope,e.player_team,"
        "i.context_route_key,i.context_policy_version,i.start_map_id "
        "FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "JOIN dungeon_room_encounters e ON e.fight_id=f.id "
        "JOIN dungeon_instances i ON i.instance_id=e.instance_id WHERE f.id=%s FOR UPDATE OF f,c,i,e",
        (fight_id,),
    ).fetchone()
    if candidate is None:
        raise ValueError("Missing certified owned terminal encounter")
    configuration = dungeon_runtime_config.pinned_configuration(
        db, candidate["context_route_key"], candidate["context_policy_version"]
    )
    selected = reviewed_roster(configuration, candidate["room_order"])
    if candidate["encounter_scope"] != "main" or candidate["fight_kind"] != "pve":
        raise ValueError("Unsupported terminal recovery encounter")
    digest = checkpoint_digest(candidate["snapshot"])
    members = db.execute(
        "SELECT p.*,false AS withdrawn FROM combat_fight_participants p WHERE fight_id=%s ORDER BY character_id FOR UPDATE",
        (fight_id,),
    ).fetchall()
    if len(members) != 1:
        raise ValueError("Certified quest recovery requires its one original owner")
    owner = members[0]
    if owner["team"] != candidate["player_team"]:
        raise ValueError("Certified terminal participant changed its original team")
    key = f"certified-quest-terminal:{fight_id}"
    old = db.execute(
        "SELECT payload FROM character_achievement_events WHERE character_id=%s AND event_key=%s",
        (owner["character_id"], key),
    ).fetchone()
    if old is not None:
        if (
            old["payload"].get("checkpoint_sha256") != digest
            or candidate["fight_status"] != "finished"
        ):
            raise ValueError("Conflicting certified terminal replay")
        return dict(old["payload"], replay=True)
    interrupted = (
        candidate["fight_status"] == "active"
        and candidate["checkpoint_status"] == "active"
        and candidate["encounter_status"] == "active"
    )
    reviewed = (
        reviewed_aborted_sha256 == digest
        and candidate["fight_status"] == "aborted"
        and candidate["checkpoint_status"] == "aborted"
        and candidate["encounter_status"] == "aborted"
    )
    if not interrupted and not reviewed:
        raise ValueError(
            "Terminal recovery requires an interruption or reviewed abort digest"
        )
    run = db.execute(
        "SELECT * FROM dungeon_room_runs WHERE instance_id=%s FOR UPDATE",
        (candidate["instance_id"],),
    ).fetchone()
    if (
        run is None
        or run["status"] != "active"
        or run["current_room"] != candidate["room_order"]
    ):
        raise ValueError("Terminal recovery no longer owns the current room")
    later = db.execute(
        "SELECT 1 FROM dungeon_room_encounters WHERE instance_id=%s AND room_order=%s AND fight_id>%s LIMIT 1",
        (candidate["instance_id"], candidate["room_order"], fight_id),
    ).fetchone()
    if later is not None:
        raise ValueError("A later encounter supersedes the certified terminal")
    group = db.execute(
        "SELECT g.*,r.asset_map_id FROM dungeon_room_spawn_receipts r JOIN combat_groups g "
        "ON g.map_id=r.asset_map_id AND g.instance_id=r.instance_id AND g.group_id=r.group_id "
        "WHERE r.instance_id=%s AND r.room_order=%s FOR UPDATE OF g",
        (candidate["instance_id"], candidate["room_order"]),
    ).fetchone()
    if (
        group is None
        or group["asset_map_id"] != candidate["start_map_id"]
        or candidate["start_map_id"] != configuration["route"]["start_map_id"]
    ):
        raise ValueError("Certified terminal lost its native group/map")
    if not (
        (group["status"] == "fighting" and group["fight_id"] == fight_id)
        or (reviewed and group["status"] == "available" and group["fight_id"] is None)
    ):
        raise ValueError("Certified terminal lost its original group reservation")
    if (
        db.execute(
            "SELECT 1 FROM combat_pve_withdrawals WHERE fight_id=%s", (fight_id,)
        ).fetchone()
        is not None
    ):
        raise ValueError("Withdrawn encounters cannot use quest terminal recovery")
    fight = projection(
        candidate["snapshot"],
        fight_id=fight_id,
        owner=owner,
        monsters=group["members"],
        player_team=candidate["player_team"],
    )
    if not owned_quest_encounters.qualified_roster(fight, group["members"], selected):
        raise ValueError("Certified terminal differs from its reviewed species roster")
    character = store.character(owner["account_id"], owner["character_id"], db)
    if (
        character["map_id"] != candidate["start_map_id"]
        or character["instance_id"] != candidate["instance_id"]
    ):
        raise ValueError("Certified terminal owner left its private encounter")
    membership = db.execute(
        "SELECT character_id FROM dungeon_instance_members WHERE instance_id=%s AND status='active' ORDER BY character_id FOR UPDATE",
        (candidate["instance_id"],),
    ).fetchall()
    if membership != [dict(character_id=owner["character_id"])]:
        raise ValueError("Certified terminal private membership changed")
    # Restore only startup-invalidated fences, never actors, damage or winner.
    if reviewed:
        db.execute(
            "UPDATE dungeon_room_encounters SET status='active',result_revision=NULL,result=NULL WHERE fight_id=%s",
            (fight_id,),
        )
        db.execute(
            "UPDATE combat_groups SET status='fighting',fight_id=%s,generation=%s,revision=revision+1 WHERE map_id=%s AND instance_id=%s AND group_id=%s",
            (
                fight_id,
                owner["session_generation"],
                group["map_id"],
                group["instance_id"],
                group["group_id"],
            ),
        )
        group["revision"] += 1
        group["generation"] = owner["session_generation"]
    db.execute("UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,))
    from wakfu_server.combat_reward_ownership import _durable_settlement_scope
    from wakfu_server import combat_reward_context, reward_policy, combat_rewards
    from wakfu_server import combat_drops, combat_drop_delivery
    from wakfu_server.combat_group_store import PersistentGroups
    from .combat_adapter import settle_participants

    with _durable_settlement_scope(db, fight, members):
        context, drop_context = combat_reward_context.settlement_contexts(
            db, fight, character, group["members"], encounter_kind="dungeon"
        )
        policy = reward_policy.resolve(
            store,
            db,
            account_id=owner["account_id"],
            generation=owner["session_generation"],
            character_id=owner["character_id"],
            fight_id=fight_id,
            context=context,
        ).policy
        reward = combat_rewards.award_shared_member(
            store,
            db,
            owner["account_id"],
            owner["session_generation"],
            owner["character_id"],
            fight,
            policy,
        )
        actor = fight.actors[owner["character_id"]]
        drops = combat_drops.resolve(
            store,
            db,
            account_id=owner["account_id"],
            generation=owner["session_generation"],
            character_id=owner["character_id"],
            fight_id=fight_id,
            monsters=[
                dict(actor_id=m["id"], reference=m["ref"]) for m in group["members"]
            ],
            prospecting_bonus=combat_drops.native_prospection_bonus(actor),
            shop_consumable_factor=combat_drops.native_shop_drop_factor(actor),
            can_loot=True,
            fight_context=drop_context,
        )
        combat_drop_delivery.apply(store, db, drops)
        lease = (
            (group["map_id"], group["instance_id"], group["group_id"]),
            group["generation"],
            fight_id,
            group["revision"],
        )
        if not PersistentGroups(store).finish(lease, defeated=True, db=db):
            raise ValueError("Certified terminal group reservation changed")
        dungeon_progression.settle_encounter(db, fight)
        settle_participants(db, store, fight, members, group["members"])
    receipt = dict(
        policy=POLICY,
        fight_id=fight_id,
        instance_id=candidate["instance_id"],
        room_order=candidate["room_order"],
        checkpoint_sha256=digest,
        checkpoint_revision=candidate["revision"],
        winner=fight.winner,
        original_actor_ids=sorted(m["id"] for m in group["members"]),
        owner=owner["character_id"],
        reviewed_abort=reviewed,
        xp=reward["xp"],
        kamas=reward["kamas"],
    )
    if not storage.record_event(db, owner["character_id"], key, receipt):
        raise ValueError("Certified terminal recovery raced")
    db.execute(
        "UPDATE fight_checkpoints SET status='ended',revision=revision+1,updated_at=%s WHERE fight_id=%s",
        (store.now(), fight_id),
    )
    return receipt


def settle_startup(store, db):
    """Preserve supported genuinely finished wins before the ordinary abort pass."""
    rows = db.execute(
        "SELECT f.id FROM combat_fights f JOIN fight_checkpoints c ON c.fight_id=f.id "
        "JOIN dungeon_room_encounters e ON e.fight_id=f.id JOIN dungeon_instances i ON i.instance_id=e.instance_id "
        "JOIN dungeon_runtime_configurations q ON q.route_key=i.context_route_key AND q.policy_version=i.context_policy_version "
        "WHERE f.status='active' AND f.fight_kind='pve' AND c.status='active' "
        "AND c.snapshot->>'phase'='finished' AND c.snapshot->'winner'=to_jsonb(e.player_team) "
        "AND (q.configuration->'topology'->'owned_quest_encounter' IS NOT NULL "
        "OR q.configuration->'topology'->'owned_story_controller' IS NOT NULL) ORDER BY f.id"
    ).fetchall()
    recovered = []
    for row in rows:
        try:
            with db.transaction():
                receipt = recover(store, db, row["id"])
        except ValueError as error:
            # A certificate rejection rolls back only this candidate. The
            # caller's ordinary interrupted-fight abort still owns its cleanup.
            # Database/programming failures must remain visible and propagate.
            logging.getLogger(__name__).warning(
                "Owned quest terminal recovery rejected fight_id=%s reason=%s",
                row["id"],
                error,
            )
        else:
            recovered.append(receipt)
    return recovered
