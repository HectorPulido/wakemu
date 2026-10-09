"""Persist actual owned captured-slot mutations in the fight's existing transaction."""
from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from wakfu_server.characters.captured_roster_store import save


def persist_captured_roster_updates(db, fight, *, owner_ids=None):
    updates = getattr(fight, "native_captured_roster_updates", {})
    if not isinstance(updates, dict):
        raise ValueError("Invalid native captured roster mutation queue")
    for key, record in updates.items():
        if not isinstance(key, str) or not key.isdecimal():
            raise ValueError("Invalid captured roster owner key")
        owner_id = int(key)
        if owner_ids is not None and owner_id not in owner_ids:
            continue
        roster = OwnedCapturedRoster.from_record(record, expected_owner_id=owner_id)
        actor = fight.actors.get(owner_id)
        if (
            actor is None
            or actor.controlled is not True
            or type(actor.owner_id) is not int
        ):
            raise ValueError(
                "Captured mutation owner is absent from controlled fight roster"
            )
        row = db.execute(
            "SELECT id,account_id,breed FROM characters WHERE id=%s AND account_id=%s "
            "AND breed=2 AND deleted_at IS NULL FOR UPDATE",
            (owner_id, actor.owner_id),
        ).fetchone()
        if row is None:
            raise ValueError("Captured mutation lacks actual owned Osamodas character")
        previous = db.execute(
            "SELECT record FROM character_captured_rosters WHERE character_id=%s FOR UPDATE",
            (owner_id,),
        ).fetchone()
        if previous is not None and previous["record"] == record:
            continue
        save(db, row, roster)


def persist_departing_captured_roster(db, fight, character):
    """Persist actual PC teardown without publishing a transaction preview.

    Call only after the health-exit owner/receipt fences have validated. The
    native biB.dnN reset releases availability without erasing captured entries
    or selection. Reconnect recovery can use a retained terminal snapshot or
    the already persisted component when only the terminal actor is hydrated.
    """
    if character.get("breed") != 2:
        return False
    from copy import deepcopy
    from .combat_captured_roster_lifecycle import restore_departing_roster

    preview = deepcopy(fight)
    if not restore_departing_roster(preview, character):
        return False
    persist_captured_roster_updates(db, preview, owner_ids={character["id"]})
    return True
