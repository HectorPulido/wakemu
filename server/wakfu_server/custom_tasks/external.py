"""World-side durable fact publication and objectives projection consumption.

The objectives worker evaluates policy. World alone authenticates gameplay facts
and delivers rewards under its existing session, inventory and account fences.
No gameplay request makes an HTTP call or waits for objective evaluation.
"""
import os
import hashlib
import re
from collections import Counter
from datetime import datetime, timezone


def enabled():
    mode = os.environ.get("WAKFU_OBJECTIVES_MODE", "local")
    if mode not in ("local", "external"):
        raise ValueError("Invalid WAKFU_OBJECTIVES_MODE")
    return mode == "external"


def enqueue_fact(db, account_id, character_id, event_key, payload):
    """Publish a server-proven fact in the caller's gameplay transaction."""
    if not enabled():
        return {"replayed": False, "updated": [], "completed": []}
    from .service import _owner
    from wakfu_server.objectives import repository

    _owner(db, account_id, character_id, True)
    result = repository.enqueue(db, account_id, character_id, event_key, payload)
    # Projection changes are asynchronous; a periodic reader refreshes cards.
    return {
        "replayed": bool(result.get("replayed", False)),
        "updated": [],
        "completed": [],
    }


def snapshot(db, character_id, *, now=None, section=None, page=1):
    """Present enabled current-period projections, including zero progress."""
    from wakfu_server.objectives import assignments, points, repository, schedules

    now = now or datetime.now(timezone.utc)
    progress = {
        (row["definition_key"], row["period_key"]): row
        for row in repository.list_progress(db, character_id)
    }
    owner = db.execute(
        "SELECT level,account_id FROM characters WHERE id=%s", (character_id,)
    ).fetchone()
    level = owner["level"] if owner is not None else 1
    if owner is None:
        return []
    assignments.ensure_for_character(
        db, owner["account_id"], character_id, level, at=now
    )
    assigned_keys = assignments.visible_keys(db, owner["account_id"], at=now)
    point_weights = points.weights(db)
    completed = {
        row["definition_key"]
        for row in progress.values()
        if row["completed_at"] is not None
    }
    result = []
    definitions = repository.list_definitions(db)
    titles = Counter(row["definition"]["title"] for row in definitions)
    policy_rows = {}
    if any(
        reward.get("kind") == "scaled"
        for row in definitions
        for reward in row["definition"]["rewards"]
    ):
        from wakfu_server.objectives.reward_policies import list_policies

        policy_rows = {row["key"]: row for row in list_policies(db)}
    for row in definitions:
        definition = row["definition"]
        if not definition["enabled"]:
            continue
        managed = assignments.managed(definition)
        if managed and row["key"] not in assigned_keys:
            continue
        bounds = definition.get("level_range")
        if (
            row["key"] not in assigned_keys
            and bounds is not None
            and not bounds["minimum"] <= level <= bounds["maximum"]
        ):
            continue
        period = schedules.period_key(definition["schedule"], now)
        if period is None:
            continue
        state = progress.get((row["key"], period))
        if (
            managed
            and definition["schedule"]["type"] == "once"
            and state
            and state["completed_at"] is not None
        ):
            continue
        reward_level = (
            assignments.assigned_level(db, owner["account_id"], row["key"], period)
            if managed
            else None
        ) or level
        counters = state["counters"] if state is not None else {}
        objectives = definition["objectives"]
        target = sum(objective["target"] for objective in objectives)
        count = sum(
            min(objective["target"], counters.get(objective["key"], 0))
            for objective in objectives
        )
        description = definition["description"]
        locked = [
            key
            for key in definition.get("prerequisite_keys", [])
            if key not in completed
        ]
        if locked:
            description += "\nLocked: complete " + ", ".join(locked) + "."
        rewards = []
        preview_rewards = []
        for reward in definition["rewards"]:
            if reward.get("kind") == "scaled":
                policy = policy_rows.get(reward["policy_key"])
                if policy is None:
                    raise ValueError("Objective reward policy is unavailable")
                band = next(
                    band
                    for band in policy["policy"]["bands"]
                    if band["minimum"] <= reward_level <= band["maximum"]
                )
                preview_rewards.extend(band["rewards"])
            else:
                preview_rewards.append(reward)
        for reward in preview_rewards:
            if reward.get("kind") == "kamas":
                rewards.append(f"{reward['amount']:,} kamas")
            elif reward.get("kind") == "random_item":
                rewards.append(
                    f"{reward['quantity']} random item(s) from up to {len(reward['references'])} level-compatible items"
                )
            elif reward["aeV"] == 5:
                rewards.append(f"{reward['ckl'][1]} x item #{reward['ckl'][0]}")
            else:
                labels = {2: "title", 3: "emote", 6: "experience"}
                rewards.append(
                    labels.get(reward["aeV"], "native reward")
                    + ": "
                    + str(reward["ckl"])
                )
        if rewards:
            description += (
                "\nReward: "
                + "; ".join(rewards)
                + ". Delivered automatically after completion."
            )
        description += f"\nPoints: {point_weights[points.category(definition)]}. Shared account progress."
        if len(objectives) > 1:
            description += "\n" + "\n".join(
                f"{objective['key']}: {min(objective['target'], counters.get(objective['key'], 0))}/{objective['target']}"
                for objective in objectives
            )
        if definition["schedule"]["type"] != "once":
            description += "\nPeriod: " + period
        visible_key = row["key"]
        if not re.fullmatch(r"[a-z0-9][a-z0-9._:-]{0,127}", visible_key):
            visible_key = (
                "objective:" + hashlib.sha256(visible_key.encode()).hexdigest()
            )
        title = definition["title"]
        if titles[title] > 1:
            title += " [" + row["key"] + "]"
        result.append(
            {
                "key": visible_key,
                "title": title,
                "description": description,
                "target": target,
                "count": count,
                "completed": state is not None and state["completed_at"] is not None,
            }
        )
    if section is None:
        return result
    from .sections import project

    projected = project(result, definitions, section, page)
    if section == "weekly" and owner is not None:
        from .sections import weekly_ranking

        projected.insert(1, weekly_ranking(db, owner["account_id"], now))
    return projected


def pending_rewards(db, character_id):
    return (
        db.execute(
            "SELECT 1 FROM objectives_rewards WHERE character_id=%s "
            "AND delivered_at IS NULL LIMIT 1",
            (character_id,),
        ).fetchone()
        is not None
    )
