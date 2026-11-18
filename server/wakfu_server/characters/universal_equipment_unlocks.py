"""Explicit universal equipment entitlements, separate from earned progression.

Hector authorized the maximum company rank and El efecto santo for existing
and future characters. No level, XP, inventory or reward outbox is modified.
"""
from copy import deepcopy

SETTING = "universal_equipment_unlocks"
VERSION = 1
SAINT_ACHIEVEMENT = 1509
SAINT_OBJECTIVE = 2825
DEFAULT = dict(
    version=VERSION,
    enabled=False,
    minimum_company_rank=12,
    completed_achievement_ids=[SAINT_ACHIEVEMENT],
)


def policy(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    selected = deepcopy(DEFAULT if row is None else row["value"])
    if (
        not isinstance(selected, dict)
        or set(selected) != set(DEFAULT)
        or type(selected["version"]) is not int
        or selected["version"] != VERSION
        or type(selected["enabled"]) is not bool
        or type(selected["minimum_company_rank"]) is not int
        or selected["minimum_company_rank"] != 12
        or selected["completed_achievement_ids"] != [SAINT_ACHIEVEMENT]
        or any(
            type(value) is not int for value in selected["completed_achievement_ids"]
        )
    ):
        raise ValueError("Invalid universal equipment entitlement policy")
    return selected


def effective_company_score(db, earned_score):
    selected = policy(db)
    if not selected["enabled"]:
        return earned_score
    from wakfu_server.company_authority import ranks

    native = next(
        row for row in ranks() if row["rank"] == selected["minimum_company_rank"]
    )
    return max(earned_score, native["minimum_score"])


def grant(db, character_id, now_ms):
    """Apply the scoped achievement once inside the caller's owner transaction."""
    from wakfu_server.achievements import storage

    selected = policy(db)
    if not selected["enabled"]:
        return False
    if type(now_ms) is not int or not 0 < now_ms < (1 << 63):
        raise ValueError("Invalid universal equipment grant clock")
    before = storage.load_locked(db, character_id)
    if SAINT_ACHIEVEMENT in before["completed"]:
        return False
    after = deepcopy(before)
    after["objectives"] = sorted(set(after["objectives"]) | {SAINT_OBJECTIVE})
    after["running"] = [
        value for value in after["running"] if value != SAINT_ACHIEVEMENT
    ]
    after["completed"] = sorted(set(after["completed"]) | {SAINT_ACHIEVEMENT})
    after["tracking"] = [
        value for value in after["tracking"] if value != SAINT_ACHIEVEMENT
    ]
    after["completion_dates"].setdefault(str(SAINT_ACHIEVEMENT), now_ms)
    after["recent"] = (after["recent"] + [dict(id=SAINT_ACHIEVEMENT, date_ms=now_ms)])[
        -255:
    ]
    # Newer lifecycle records retain independent active flags. Existing active
    # history is preserved; an explicit completed entitlement resolves only its
    # own otherwise-unknown completion, never another quest or acceptance clock.
    if "active_unknown" in after:
        after["active_unknown"] = [
            value for value in after["active_unknown"] if value != SAINT_ACHIEVEMENT
        ]
    storage.store(db, character_id, after)
    storage.record_event(
        db,
        character_id,
        "universal-equipment-unlocks:v1:1509",
        dict(
            schema="wakemu.universal-equipment-unlocks.v1",
            achievement=SAINT_ACHIEVEMENT,
            objective=SAINT_OBJECTIVE,
            rewards_granted=False,
        ),
    )
    return True
