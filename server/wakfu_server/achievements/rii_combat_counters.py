"""Rii quest counters from authenticated, already settled combat victories.

The client names the Wodent target; the selected local breed identities and
per-defeated-monster counting are a reconstruction, not an original receipt.
"""
from . import counter_missions, storage, wire


# The installed monster catalog calls both of these Wodent; both occur on Rii.
# A secondary Rii guide explicitly includes the mother alongside Wodents.
WODENT_BREEDS = frozenset({5455, 5456, 5525})


def settle(db, store, character, event):
    """Count defeated original Wodents, once per victory and character.

    The caller supplies the authenticated event returned by achievements.service
    and isolates this optional settlement from the combat/reward transaction.
    """
    if (character.get("map_id"), character.get("instance_id")) != (1385, 0):
        return []
    fight_id = event.get("fight_id")
    breeds = event.get("original_breeds")
    if (
        type(fight_id) is not int
        or fight_id <= 0
        or not isinstance(breeds, list)
        or any(type(breed) is not int or breed <= 0 for breed in breeds)
    ):
        raise ValueError("Invalid authenticated fight event")
    amount = sum(breed in WODENT_BREEDS for breed in breeds)
    if not amount:
        return []
    from .service import _owner

    _owner(db, character)
    before = storage.load_locked(db, character["id"])
    if 5145 not in before["running"] or 10579 in before["objectives"]:
        return []
    row = db.execute(
        "SELECT data FROM native_quest_metadata_definitions WHERE revision="
        "(SELECT revision FROM native_quest_metadata_releases ORDER BY imported_at DESC LIMIT 1) "
        "AND definition_id=%s",
        (5145,),
    ).fetchone()
    if row is None:
        raise ValueError("Missing Rii Wodent quest definition")
    definition = row["data"]["native"]
    if (5145, 10579, 755, 3) not in counter_missions.bindings([definition]).get(
        755, ()
    ):
        raise ValueError("Wodent kill counter differs from native definition")
    now_ms = int(store.now().timestamp() * 1000)
    after, objectives = before, []
    for _ in range(amount):
        after, intents, added, completed = counter_missions.advance(
            after, [definition], 755, character=character, store=store, now_ms=now_ms
        )
        if intents or completed:
            raise ValueError("Unexpected Wodent kill quest completion")
        objectives.extend(added)
    if not storage.record_event(
        db,
        character["id"],
        f"rii-wodent-victory:{fight_id}",
        {"kind": "rii_wodent_victory", "fight_id": fight_id, "count": amount},
    ):
        return []
    storage.store(db, character["id"], after)
    return wire.changes(
        character["id"],
        before,
        after,
        objectives,
        [],
        now_ms,
        definitions={5145: definition},
    )
