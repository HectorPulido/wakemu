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


def _evaluate(
    store, criterion, *, character, destination_map_id=None, minimum_enforced
):
    from wakfu_server.maps import dungeon_achievement_authority, dungeon_criteria
    from wakfu_server.maps.seasonal_access import open_event_calendar

    selected = policy(store)
    criterion = open_event_calendar(criterion, destination_map_id=destination_map_id)
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
        bypass_minimum_level=not minimum_enforced,
    )


def evaluate(store, criterion, *, character, destination_map_id=None):
    from .instance_entry_level import enforced

    with store.connection() as db:
        minimum_enforced = enforced(db)
    return _evaluate(
        store,
        criterion,
        character=character,
        destination_map_id=destination_map_id,
        minimum_enforced=minimum_enforced,
    )


def minimum_offer_allowed(db, criterion, *, character, destination_map_id):
    """Offer a server-owned entrance only when its waived minimum blocks UI.

    Both evaluations use real owner facts and identical non-level policies.
    The offer never grants entry: World revalidates the source, party, costs,
    session and current policy in its existing transition transaction.
    """
    from contextlib import contextmanager
    import time
    from .instance_entry_level import enforced

    if enforced(db):
        return False
    now = time.time()

    class SnapshotStore:
        @contextmanager
        def connection(self):
            yield db

        def clock(self):
            return now

    actor = dict(character)
    if "GetItemQuantity" in criterion:
        from wakfu_server.inventory_items import load as load_items
        from wakfu_server.items.quest_inventory import load as load_quests
        from wakfu_server.items.account_quest_inventory import load as load_account
        from wakfu_server.characters.exploration_secrets import load as load_secrets

        actor["exploration_secrets"] = load_secrets(db)
        actor["inventory_items"] = load_items(db, actor["id"])
        actor["quest_items"] = load_quests(db, actor["id"])
        actor["account_quest_items"] = load_account(db, actor["account_id"])
    store = SnapshotStore()
    try:
        strict = _evaluate(
            store,
            criterion,
            character=actor,
            destination_map_id=destination_map_id,
            minimum_enforced=True,
        )
        relaxed = _evaluate(
            store,
            criterion,
            character=actor,
            destination_map_id=destination_map_id,
            minimum_enforced=False,
        )
    except ValueError:
        return False
    return strict is False and relaxed is True
