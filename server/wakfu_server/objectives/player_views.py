"""Player-only projection of definitions, progress and public challenge results."""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from datetime import datetime, timezone
from . import repository, rankings, player_auth, player_actions, assignments, points
from .schedules import period_key
from wakfu_server.custom_tasks.sections import category


def reward_preview(rewards, level, policies):
    """Show eligible pools, never draw randomness or reserve an entitlement."""
    result = []
    for reward in rewards:
        if reward.get("kind") != "scaled":
            result.append(dict(reward))
            continue
        policy = policies.get(reward["policy_key"])
        if policy is None:
            continue
        band = next(
            (b for b in policy["bands"] if b["minimum"] <= level <= b["maximum"]), None
        )
        if band:
            result.extend(dict(r) for r in band["rewards"])
    return result


def snapshot(db, identity):
    identity = player_auth.resolve_account(db, identity, lock=True)
    now = datetime.now(timezone.utc)
    actor = db.execute(
        "SELECT id,name,level,instance_id FROM characters WHERE id=%s AND account_id=%s AND deleted_at IS NULL",
        (identity["character_id"], identity["account_id"]),
    ).fetchone()
    if actor is None:
        raise player_auth.Unauthorized("Character unavailable")
    if player_auth.live_identity(db, identity):
        assignments.ensure_for_character(
            db, identity["account_id"], actor["id"], actor["level"], at=now
        )
    assigned_keys = assignments.visible_keys(db, identity["account_id"], at=now)
    point_weights = points.weights(db)
    definitions = repository.list_definitions(db)
    progress_rows = repository.list_progress(db, actor["id"])
    progress = {
        (row["definition_key"], row["period_key"]): row for row in progress_rows
    }
    completed = {
        row["definition_key"]
        for row in progress_rows
        if row["completed_at"] is not None
    }
    policies = {
        r["key"]: r["policy"]
        for r in db.execute(
            "SELECT key,policy FROM objectives_reward_policies"
        ).fetchall()
    }
    actions = [
        player_actions.public_action(a)
        for a in player_actions.allowed_actions(db, identity)
    ]
    sections = {
        key: []
        for key in (
            "board",
            "daily",
            "weekly",
            "almanax",
            "achievements",
            "first_steps",
            "pvp",
            "missions",
        )
    }
    for row in definitions:
        definition = row["definition"]
        band = definition.get(
            "level_range", dict(minimum=1, maximum=MAX_CHARACTER_LEVEL)
        )
        if not definition["enabled"] or (
            definition["key"] not in assigned_keys
            and not band["minimum"] <= actor["level"] <= band["maximum"]
        ):
            continue
        if assignments.managed(definition) and definition["key"] not in assigned_keys:
            continue
        period = period_key(definition["schedule"], now)
        if period is None:
            continue
        reward_level = (
            assignments.assigned_level(
                db, identity["account_id"], definition["key"], period
            )
            if assignments.managed(definition)
            else None
        ) or actor["level"]
        saved = progress.get((definition["key"], period))
        if (
            assignments.managed(definition)
            and definition["schedule"]["type"] == "once"
            and saved
            and saved["completed_at"] is not None
        ):
            continue
        counters = saved["counters"] if saved else {}
        objectives = [
            dict(
                key=o["key"],
                current=min(counters.get(o["key"], 0), o["target"]),
                target=o["target"],
            )
            for o in definition["objectives"]
        ]
        prerequisites = definition.get("prerequisite_keys", [])
        state = (
            "completed"
            if saved and saved["completed_at"] is not None
            else "locked"
            if any(dep not in completed for dep in prerequisites)
            else "in_progress"
            if any(o["current"] for o in objectives)
            else "available"
        )
        card_actions = [
            a
            for a in actions
            if a.get("definition_key") == definition["key"]
            or (
                a["key"].startswith("weekly.")
                and any(
                    o["event"] == "challenge_completed"
                    for o in definition["objectives"]
                )
            )
        ]
        card = dict(
            key=definition["key"],
            title=definition["title"],
            description=definition["description"],
            kind=definition["kind"],
            achievement_type=achievement_type(definition),
            points=point_weights[points.category(definition)],
            schedule_type=definition["schedule"]["type"],
            scope=definition.get("scope", "character"),
            period_key=period,
            state=state,
            objectives=objectives,
            progress=sum(o["current"] / o["target"] for o in objectives)
            / len(objectives),
            reward_level=reward_level,
            rewards=reward_preview(definition["rewards"], reward_level, policies),
            prerequisite_keys=prerequisites,
            actions=card_actions if state != "locked" else [],
        )
        section = (
            "first_steps"
            if definition["kind"] == "onboarding"
            else category(definition)
        )
        if section == "tasks":
            section = "board"
        sections[section].append(card)
    decorate_achievement_zones(db, sections["achievements"], definitions)
    decorate_reward_names(db, sections)
    for name, cards in sections.items():
        cards.sort(
            key=lambda c: (
                c["key"]
                if name == "first_steps"
                else (c["state"] == "completed", c["key"])
            )
        )
    ranking_rows = points.list_rankings(db, limit=100)
    names = {
        r["id"]: r["name"]
        for r in db.execute(
            "SELECT id,name FROM characters WHERE id=ANY(%s::bigint[])",
            ([r["character_id"] for r in ranking_rows],),
        ).fetchall()
    }
    ranking = [
        dict(
            rank=r["rank"],
            bracket=r["bracket"],
            points=r["points"],
            character_name=names.get(r["character_id"], "Unknown"),
            is_self=r["account_id"] == identity["account_id"],
        )
        for r in ranking_rows
    ]
    history = db.execute(
        "SELECT w.name AS winner_name,l.name AS loser_name,o.settled_at AS finished_at FROM friendly_duel_outcomes o JOIN characters w ON w.id=o.winner_character_id JOIN characters l ON l.id=o.loser_character_id WHERE w.account_id<>l.account_id ORDER BY o.settled_at DESC,o.fight_id DESC LIMIT 20"
    ).fetchall()
    from . import pvp, hunts

    hunt = hunts.snapshot(db, identity)
    if hunt:
        decorate_reward_names(db, {"hunt": [{"rewards": hunt.get("rewards", [])}]})
    pvp_view = pvp.snapshot(db, identity)
    available_by_key = {action["key"]: action for action in actions}
    pvp_rewards = []
    for event in ([pvp_view["current"]] if pvp_view["current"] else []) + pvp_view[
        "history"
    ]:
        event["actions"] = [
            available_by_key[a["key"]]
            for a in event["actions"]
            if a["key"] in available_by_key
        ]
        pvp_rewards.extend(
            reward for rewards in event["rewards"].values() for reward in rewards
        )
    decorate_reward_names(db, {"pvp": [{"rewards": pvp_rewards}]})
    connected = player_auth.live_identity(db, identity) is not None
    connection = dict(
        online=connected,
        actions_available=any(a["enabled"] for a in actions),
        reason=None
        if connected
        else "Connect this character in World to use game actions",
    )
    recovery_actions = (
        [
            dict(a, label="Leave previous challenge")
            for a in actions
            if a["key"] in ("weekly.return", "weekly.abandon")
        ]
        if actor["instance_id"] != 0
        else []
    )
    return dict(
        recovery_actions=recovery_actions,
        connection=connection,
        actor={key: actor[key] for key in ("id", "name", "level")},
        week_key=rankings.week_key(now),
        generated_at=now,
        sections=sections,
        ranking=ranking,
        actions=actions,
        challenge=None,
        hunt=hunt,
        pvp=pvp_view,
        pvp_history=history,
        completed_achievements=sum(
            c["state"] == "completed" for c in sections["achievements"]
        ),
    )


def decorate_reward_names(db, sections):
    """Use indexed native item names; never copy the full equipment catalogue."""
    rewards = [
        r for cards in sections.values() for card in cards for r in card["rewards"]
    ]
    refs = set()
    for reward in rewards:
        if reward.get("aeV") == 5:
            refs.add(str(reward["ckl"][0]))
        elif reward.get("kind") == "random_item":
            refs.update(str(ref) for ref in reward["references"])
    if not refs:
        return
    names = {
        row["record_key"]: row["payload"].get("name")
        for row in db.execute(
            "SELECT record_key,payload FROM native_catalog_records WHERE revision=(SELECT revision FROM native_catalog_active WHERE id=1) AND path='item-stack-rules.json' AND collection='items' AND record_key=ANY(%s::text[])",
            (sorted(refs),),
        ).fetchall()
    }
    for reward in rewards:
        if reward.get("aeV") == 5 and names.get(str(reward["ckl"][0])):
            reward["name"] = names[str(reward["ckl"][0])]
        elif reward.get("kind") == "random_item":
            reward["item_names"] = {
                str(ref): names[str(ref)]
                for ref in reward["references"]
                if names.get(str(ref))
            }


def decorate_achievement_zones(db, cards, definitions):
    """Group dungeon achievements by their native public entry geography."""
    names_row = db.execute(
        "SELECT value FROM settings WHERE name='admin_map_names'"
    ).fetchone()
    names = names_row["value"] if names_row else {}
    dungeon_maps = {
        int(row["dungeon_id"]): int(row["map_id"])
        for row in db.execute(
            "SELECT c.configuration->'route'->>'definition_id' AS dungeon_id,c.configuration->'route'->>'entry_map_id' AS map_id FROM dungeon_runtime_configurations c JOIN dungeon_runtime_active_configurations a USING(route_key,policy_version)"
        ).fetchall()
        if row["dungeon_id"] is not None and row["map_id"] is not None
    }
    definitions_by_key = {row["key"]: row["definition"] for row in definitions}
    for card in cards:
        filters = [
            objective.get("filters", {})
            for objective in definitions_by_key[card["key"]]["objectives"]
        ]
        map_ids = {
            value
            for item in filters
            for value in (
                [item.get("map_id")]
                if type(item.get("map_id")) is int
                else item.get("map_id", [])
            )
            if type(value) is int
        }
        dungeon_ids = {
            value
            for item in filters
            for value in (
                [item.get("dungeon_id")]
                if type(item.get("dungeon_id")) is int
                else item.get("dungeon_id", [])
            )
            if type(value) is int
        }
        map_ids.update(
            dungeon_maps[value] for value in dungeon_ids if value in dungeon_maps
        )
        parts = card["key"].split(".")
        map_id = next(iter(map_ids)) if len(map_ids) == 1 else None
        if map_id is not None:
            pass
        elif len(parts) >= 3 and parts[-2] == "map" and parts[-1].isdigit():
            map_id = int(parts[-1])
        elif len(parts) >= 4 and parts[-3] == "region" and parts[-2].isdigit():
            map_id = int(parts[-2])
        elif len(parts) >= 3 and parts[-2] == "dungeon" and parts[-1].isdigit():
            map_id = dungeon_maps.get(int(parts[-1]))
        card["zone"] = (
            dict(
                key="map." + str(map_id),
                name=names.get(str(map_id), "Map " + str(map_id)),
            )
            if map_id is not None
            else dict(key="account", name="Account achievements")
        )


_EVENT_ACHIEVEMENT_TYPES = {
    "dungeon_completed": "dungeons",
    "map_entered": "places",
    "map_visited": "places",
    "region_entered": "places",
    "zone_entered": "places",
    "original_monster_killed": "monsters",
    "public_hunt_completed": "monsters",
    "item_crafted": "crafting",
    "recipe_crafted": "crafting",
    "profession_level_reached": "professions",
    "account_profession_level_progressed": "professions",
    "monster_seed_planted": "gathering",
    "resource_harvested": "gathering",
    "pvp_completed": "pvp",
    "hourly_pvp_completed": "pvp",
    "combat_completed": "combat",
    "challenge_completed": "combat",
    "level_reached": "characters",
    "character_level_reached": "characters",
    "account_level_reached": "characters",
    "account_character_level_progressed": "characters",
    "shop_opened": "account",
}


def achievement_type(definition):
    """Classify by source facts, independently of authored keys or map names."""
    categories = {
        _EVENT_ACHIEVEMENT_TYPES.get(objective["event"], "other")
        for objective in definition["objectives"]
    }
    return next(iter(categories)) if len(categories) == 1 else "other"
