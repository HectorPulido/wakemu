"""Lease-owned world facing, distinct from sequenced fight actions."""
import struct


def packet(character_id, direction):
    if type(character_id) is not int or not 0 < character_id < 2**63:
        raise ValueError("Invalid world actor")
    if type(direction) is not int or not 0 <= direction <= 7:
        raise ValueError("Invalid world direction")
    return 12401, struct.pack(">qB", character_id, direction)


def save(store, account_id, generation, character_id, direction, *, outside=False):
    outgoing = packet(character_id, direction)
    if type(outside) is not bool:
        raise ValueError("Invalid orientation context")
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        if (
            outside
            and db.execute(
                "SELECT 1 FROM combat_fights f JOIN combat_fight_participants p "
                "ON p.fight_id=f.id WHERE p.character_id=%s AND p.account_id=%s "
                "AND f.status IN ('placement','active') LIMIT 1",
                (character_id, account_id),
            ).fetchone()
            is not None
        ):
            raise ValueError("World orientation requires an outside actor")
        changed = db.execute(
            "UPDATE characters SET direction=%s WHERE id=%s AND account_id=%s RETURNING id",
            (direction, character_id, account_id),
        ).fetchone()
        if changed is None:
            raise ValueError("Unknown world orientation actor")
    return {"direction": direction, "packet": outgoing}
