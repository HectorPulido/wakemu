"""Shared account objectives, source deduplication and a native Wakfu beginner route."""
from psycopg.types.json import Jsonb
from .engine import increment


def definitions():
    """Use only facts already emitted by World and catalog-qualified rewards."""
    stages = [
        (
            "Welcome to Astrub",
            "Enter Astrub through a world transition.",
            [("arrive", "map_entered", {"map_id": 527}, 1)],
        ),
        (
            "Meet the Gobballs",
            "Defeat three original Gobball-family monsters. Summons do not count.",
            [
                (
                    "gobballs",
                    "original_monster_killed",
                    {"references": [1, 2, 3, 39, 41, 44, 4085, 4086]},
                    3,
                )
            ],
        ),
        (
            "Feathers and wool",
            "Defeat two original Tofus and one original Gobball.",
            [
                ("tofus", "original_monster_killed", {"references": [4, 5]}, 2),
                (
                    "gobball",
                    "original_monster_killed",
                    {"references": [1, 2, 3, 39, 41, 44, 4085, 4086]},
                    1,
                ),
            ],
        ),
        (
            "Give nature a hand",
            "Successfully plant a Gobball seed. Failed planting does not count.",
            [
                (
                    "plant",
                    "monster_seed_planted",
                    {
                        "family_id": 68,
                        "seed_reference": 7361,
                        "resource_reference": 192,
                    },
                    1,
                )
            ],
        ),
        (
            "Practice makes progress",
            "Win three completed PvE battles after unlocking this stage.",
            [("wins", "combat_completed", {"won": True, "fight_kind": "pve"}, 3)],
        ),
        (
            "Beneath Astrub",
            "Enter the Astrub Sewers through a world transition.",
            [("sewers", "map_entered", {"map_id": 546}, 1)],
        ),
        (
            "Your first dungeon",
            "Complete Gobball Pastures or The Tofuhouse. Entering a dungeon is not completion.",
            [("dungeon", "dungeon_completed", {"dungeon_id": [90, 27]}, 1)],
        ),
    ]
    result = []
    for index, (title, description, objectives) in enumerate(stages, 1):
        identity = f"onboarding-v1.{index:02d}"
        result.append(
            dict(
                key=identity,
                title=title,
                description=description,
                kind="onboarding",
                scope="account",
                enabled=True,
                schedule={"type": "once", "timezone": "America/Bogota"},
                prerequisite_keys=[f"onboarding-v1.{index-1:02d}"] if index > 1 else [],
                objectives=[
                    dict(key=k, event=e, filters=f, target=t)
                    for k, e, f, t in objectives
                ],
                rewards=[{"kind": "scaled", "policy_key": "content-v1.daily"}],
            )
        )
    return result


def admit_source(db, event):
    """The same fight credited to several heroes is one fact for their account."""
    payload = event["payload"]
    source = payload.get("fight_id")
    identity = (
        f"{payload['kind']}:fight:{source}"
        if source is not None
        else f"{payload['kind']}:{event['event_key']}"
    )
    row = db.execute(
        "INSERT INTO objectives_account_sources(account_id,source_key,event_id) VALUES(%s,%s,%s) "
        "ON CONFLICT DO NOTHING RETURNING event_id",
        (event["account_id"], identity, event["id"]),
    ).fetchone()
    return row is not None


def advance(db, event, rule, revision, period, completed_before, reserve_rewards):
    """Called in the evaluator transaction; payout is frozen to its completing actor."""
    if any(key not in completed_before for key in rule["prerequisite_keys"]):
        return 0
    deltas = {o["key"]: increment(o, event["payload"]) for o in rule["objectives"]}
    if not any(deltas.values()):
        return 0
    prior = db.execute(
        "SELECT * FROM objectives_account_progress WHERE account_id=%s AND definition_key=%s AND period_key=%s FOR UPDATE",
        (event["account_id"], rule["key"], period),
    ).fetchone()
    if prior and prior["completed_at"]:
        return 0
    counters = dict(prior["counters"]) if prior else {}
    for objective in rule["objectives"]:
        name = objective["key"]
        from .progression import ABSOLUTE_EVENTS

        if objective["event"] in ABSOLUTE_EVENTS:
            counters[name] = min(
                objective["target"], max(counters.get(name, 0), deltas[name])
            )
        else:
            counters[name] = min(
                objective["target"], counters.get(name, 0) + deltas[name]
            )
    done = all(counters[o["key"]] >= o["target"] for o in rule["objectives"])
    completed = event["occurred_at"] if done else None
    db.execute(
        "INSERT INTO objectives_account_progress(account_id,definition_key,period_key,definition_revision,counters,completed_at,reward_character_id) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s) ON CONFLICT(account_id,definition_key,period_key) DO UPDATE SET "
        "counters=EXCLUDED.counters,completed_at=EXCLUDED.completed_at,reward_character_id=EXCLUDED.reward_character_id,updated_at=CURRENT_TIMESTAMP",
        (
            event["account_id"],
            rule["key"],
            period,
            revision,
            Jsonb(counters),
            completed,
            event["character_id"] if done else None,
        ),
    )
    if done:
        db.execute(
            "INSERT INTO objectives_progress(character_id,definition_key,period_key,definition_revision,counters,completed_at) "
            "VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(character_id,definition_key,period_key) DO UPDATE SET "
            "counters=EXCLUDED.counters,completed_at=EXCLUDED.completed_at",
            (
                event["character_id"],
                rule["key"],
                period,
                revision,
                Jsonb(counters),
                completed,
            ),
        )
        from . import assignments

        reward_level = (
            assignments.assigned_level(db, event["account_id"], rule["key"], period)
            if assignments.managed(rule)
            else event["character_level"]
        )
        if reward_level is None:
            raise ValueError("Assigned objective source level is unavailable")
        reserve_rewards(
            db,
            event["character_id"],
            rule,
            period,
            level=reward_level,
            policies=event["reward_policies"],
        )
        from .points import award_completion

        award_completion(db, event, rule, period)
    for character in db.execute(
        "SELECT id FROM characters WHERE account_id=%s AND deleted_at IS NULL",
        (event["account_id"],),
    ).fetchall():
        db.execute(
            "SELECT pg_notify('wakemu_objectives_updates',%s)", (str(character["id"]),)
        )
    return 1
