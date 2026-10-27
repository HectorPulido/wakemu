"""Restore native captured availability after an attested interrupted fight."""
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    roster_from_character,
)
from wakfu_server.characters.captured_roster_store import save


def reconcile_aborted(db, character):
    """Run inside owned exploration initialization after the character lock.

    A capture stays unavailable while its live fight owns it. Only the latest
    durable membership, an aborted checkpoint and its actual controlled owner
    can attest the missing native PC teardown. Never replace stored descriptors
    or selection with the checkpoint's older values.
    """
    if character.get("breed") != 2:
        return False
    current = roster_from_character(character)
    if current is None or all(
        entry is None or current.available[index]
        for index, entry in enumerate(current.slots)
    ):
        return False
    witness = db.execute(
        "SELECT f.id,f.status,c.status AS checkpoint_status,c.snapshot "
        "FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
        "LEFT JOIN fight_checkpoints c ON c.fight_id=f.id "
        "WHERE p.character_id=%s AND p.account_id=%s "
        "AND NOT EXISTS (SELECT 1 FROM combat_fight_participants live "
        "JOIN combat_fights running ON running.id=live.fight_id "
        "WHERE live.character_id=p.character_id "
        "AND running.status IN ('placement','active')) "
        "ORDER BY f.id DESC LIMIT 1 FOR SHARE OF f,p",
        (character["id"], character["account_id"]),
    ).fetchone()
    if (
        witness is None
        or witness["status"] != "aborted"
        or witness["checkpoint_status"] != "aborted"
    ):
        return False
    state = witness["snapshot"]
    if not isinstance(state, dict):
        raise ValueError("Aborted capture recovery lacks checkpoint state")
    key = str(character["id"])
    actor = state.get("actors", {}).get(key)
    if (
        not isinstance(actor, dict)
        or actor.get("id") != character["id"]
        or actor.get("controlled") is not True
        or actor.get("owner_id") != character["account_id"]
    ):
        raise ValueError("Aborted capture recovery lacks actual controlled owner")
    source = state.get("native_captured_rosters", {}).get(key)
    if source is None:
        source = state.get("native_captured_roster_updates", {}).get(key)
    if source is None:
        return False
    previous = OwnedCapturedRoster.from_record(
        source, expected_owner_id=character["id"]
    )
    if current.slots != previous.slots or any(
        entry is not None and not current.available[index] and previous.available[index]
        for index, entry in enumerate(current.slots)
    ):
        return False  # A later capture/component mutation is not this teardown.
    from wakfu_server.combat_captured_roster_lifecycle import reset_availability

    save(db, character, reset_availability(current))
    return True
