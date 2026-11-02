"""Restore owned captured availability after a durable interrupted-fight abort."""
from wakfu_server.characters.captured_roster import roster_from_character
from wakfu_server.characters.captured_roster_store import save


def reconcile_aborted(db, character):
    """Run inside owned exploration initialization after the character lock.

    Durable real-character membership supplies PC ownership. A latest aborted
    fight without any live membership attests its lost teardown. Historical
    actor/component snapshots are not authoritative over the current owned
    roster; never copy old descriptors, selection, health or inventory from one.
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
        "SELECT f.id,f.status FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.character_id=%s AND p.account_id=%s "
        "AND NOT EXISTS (SELECT 1 FROM combat_fight_participants live "
        "JOIN combat_fights running ON running.id=live.fight_id "
        "WHERE live.character_id=p.character_id "
        "AND running.status IN ('placement','active')) "
        "ORDER BY f.id DESC LIMIT 1 FOR SHARE OF f,p",
        (character["id"], character["account_id"]),
    ).fetchone()
    if witness is None or witness["status"] != "aborted":
        return False
    from wakfu_server.combat_captured_roster_lifecycle import reset_availability

    # Native biB.dnN -> eHR/bPo.fxn fills the current component's ten flags.
    # Occupied descriptors become unavailable only when a live summon consumes
    # them. No such fight remains; imported or later-edited descriptors survive.
    save(db, character, reset_availability(current))
    return True
