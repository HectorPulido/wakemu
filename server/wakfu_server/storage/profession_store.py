"""Owned profession levels only; no invented XP totals or XP progression curve."""
from .inventory_items import _lease


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS character_professions(
        character_id INTEGER NOT NULL REFERENCES characters(id) ON DELETE CASCADE,
        profession_id INTEGER NOT NULL CHECK(profession_id>0),
        level INTEGER NOT NULL CHECK(level BETWEEN 0 AND 200),
        PRIMARY KEY(character_id,profession_id))"""
    )


def _validate(profession_id):
    if type(profession_id) is not int or not 0 < profession_id < 2**31:
        raise ValueError("Invalid profession identity")


def level(store, account_id, generation, character_id, profession_id):
    _validate(profession_id)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        schema(db)
        row = db.execute(
            "SELECT level FROM character_professions WHERE character_id=? AND profession_id=?",
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
        db.execute("BEGIN IMMEDIATE")
        _lease(store, db, account_id, generation, character_id)
        schema(db)
        for profession_id in ids:
            db.execute(
                "INSERT OR IGNORE INTO character_professions VALUES(?,?,0)",
                (character_id, profession_id),
            )
        levels = {
            row["profession_id"]: row["level"]
            for row in db.execute(
                "SELECT * FROM character_professions WHERE character_id=?",
                (character_id,),
            )
        }
    # cus12675 is safe to replay: native eTo.j handles an already known craft.
    return dict(levels=levels, packets=[(12675, struct.pack(">i", i)) for i in ids])


def learned(store, account_id, generation, character_id, profession_id):
    _validate(profession_id)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        schema(db)
        return (
            db.execute(
                "SELECT 1 FROM character_professions WHERE character_id=? AND profession_id=?",
                (character_id, profession_id),
            ).fetchone()
            is not None
        )
