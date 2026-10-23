"""Flat native item XP grants inside the caller's inventory transaction."""
from psycopg.pq import TransactionStatus

from wakfu_server.progression import XP_BY_LEVEL, character_xp


def award_item_xp(store, db, account_id, generation, character_id, amount):
    """Return the refreshed character and native exploration update packets.

    The caller owns the account/character lease locks, outside-combat check,
    inventory consumption and action receipt. No transaction is opened here;
    a rejected grant rolls back together with the consumed source item.
    Native GIVE_XP amounts are flat, independent of combat reward multipliers.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Item XP requires an active inventory transaction")
    if type(amount) is not int or not 0 < amount < 2**63:
        raise ValueError("Invalid native item XP amount")
    character = store.character(account_id, character_id, db)
    start_xp = character_xp(character)
    total = start_xp + amount
    if total >= 2**63:
        raise ValueError("Item XP total exceeds native signed64 storage")
    level = max(
        character["level"],
        max(level for level, threshold in XP_BY_LEVEL.items() if threshold <= total),
    )
    db.execute(
        "UPDATE character_progression SET xp=%s WHERE character_id=%s",
        (total, character_id),
    )
    if level != character["level"]:
        db.execute(
            "UPDATE characters SET level=%s WHERE account_id=%s AND id=%s",
            (level, account_id, character_id),
        )
        from wakfu_server.characters.dungeon_modulation_health import reconcile

        # The inventory caller already authorized the selected character or an
        # active hero. This shared boundary refreshes effective build health
        # without requiring that the recipient be the selected main character.
        # It preserves canonical wounds, death and the existing regeneration
        # rate, and cannot finalize a pending fight return or resurrect anyone.
        (updated,) = reconcile(store, db, (character_id,))
    else:
        updated = store.character(account_id, character_id, db)
    from wakfu_server.combat_lifecycle import outside_progression

    return {
        "character": updated,
        "packets": [outside_progression(updated)],
        "xp": amount,
        "start_xp": start_xp,
        "end_xp": total,
        "start_level": character["level"],
        "end_level": level,
    }
