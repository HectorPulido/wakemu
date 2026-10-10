"""Database policy for mission-free dungeon entrances, never internal doors.

Waived predicates are unknown in a three-valued expression. A required false
level/date/mode predicate still denies entry, while a mission-only alternative
can authorize it. No achievement or character-state facts are manufactured.
"""

SETTING = "dungeon_entry_access_policy"
DEFAULT = {
    "version": 1,
    "bypass_mission_prerequisites": True,
    "bypass_state_prerequisites": True,
}


def policy(store):
    with store.connection() as db:
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s", (SETTING,)
        ).fetchone()
    value = None if row is None else row["value"]
    if (
        not isinstance(value, dict)
        or set(value) != set(DEFAULT)
        or type(value.get("version")) is not int
        or value["version"] != 1
        or any(type(value.get(key)) is not bool for key in DEFAULT if key != "version")
    ):
        raise ValueError("Dungeon entrance access policy is missing or invalid")
    return value


def evaluate(store, criterion, *, character):
    from wakfu_server.maps import dungeon_achievement_authority, dungeon_criteria

    selected = policy(store)
    authority = None
    if not selected["bypass_mission_prerequisites"] and any(
        name in criterion
        for name in (
            "IsAchievementRunning",
            "IsAchievementComplete",
            "IsAchievementObjectiveComplete",
        )
    ):
        authority = dungeon_achievement_authority.queries(store, character["id"])
    return dungeon_criteria.evaluate(
        store,
        criterion,
        character=character,
        queries=authority,
        bypass_mission_prerequisites=selected["bypass_mission_prerequisites"],
        bypass_state_prerequisites=selected["bypass_state_prerequisites"],
    )
