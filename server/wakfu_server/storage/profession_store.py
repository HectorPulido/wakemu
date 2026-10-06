"""Owned profession levels only; no invented XP totals or XP progression curve."""
from .inventory_items import _lease


def _validate(profession_id):
    if type(profession_id) is not int or not 0 < profession_id < 2**31:
        raise ValueError("Invalid profession identity")


def level(store, account_id, generation, character_id, profession_id):
    _validate(profession_id)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        row = db.execute(
            "SELECT level FROM character_professions WHERE character_id=%s AND profession_id=%s",
            (character_id, profession_id),
        ).fetchone()
        return 0 if row is None else row["level"]


def ensure_learned(store, account_id, generation, character_id, profession_ids):
    """Explicit local baseline learning at level0; preserve existing own levels."""
    import json, struct
    from .paths import DATA_ROOT

    known = set(
        json.loads((DATA_ROOT / "profession-actions.json").read_text())[
            "profession_ids"
        ]
    )
    ids = list(profession_ids)
    if len(set(ids)) != len(ids) or any(
        type(i) is not int or i not in known for i in ids
    ):
        raise ValueError("Unknown native profession requested")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        for profession_id in ids:
            db.execute(
                "INSERT INTO character_professions VALUES(%s,%s,0) ON CONFLICT(character_id,profession_id) DO NOTHING",
                (character_id, profession_id),
            )
        levels = {
            row["profession_id"]: row["level"]
            for row in db.execute(
                "SELECT * FROM character_professions WHERE character_id=%s",
                (character_id,),
            )
        }
    # cus12675 is safe to replay: native eTo.j handles an already known craft.
    return dict(levels=levels, packets=[(12675, struct.pack(">i", i)) for i in ids])


def learned(store, account_id, generation, character_id, profession_id):
    _validate(profession_id)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        return (
            db.execute(
                "SELECT 1 FROM character_professions WHERE character_id=%s AND profession_id=%s",
                (character_id, profession_id),
            ).fetchone()
            is not None
        )
