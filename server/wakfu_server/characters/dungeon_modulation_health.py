"""Reconcile temporary dungeon health at already-authorized durable boundaries.

Callers own the transaction and membership/session authorization. Wounds and
death remain canonical; changing a maximum never heals a character.
"""
from psycopg.pq import TransactionStatus


def reconcile(store, db, character_ids):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Dungeon health reconciliation requires a transaction")
    identities = tuple(character_ids)
    if any(type(identity) is not int or identity <= 0 for identity in identities):
        raise ValueError("Invalid dungeon health character identity")
    identities = sorted(set(identities))
    if not identities:
        return ()
    rows = db.execute(
        "SELECT id,account_id,hp,max_hp FROM characters "
        "WHERE id=ANY(%s) AND deleted_at IS NULL ORDER BY id FOR UPDATE",
        (identities,),
    ).fetchall()
    if [row["id"] for row in rows] != identities:
        raise ValueError("Dungeon health member is unavailable")
    from wakfu_server.characters.dungeon_modulation import effective_health_max
    from wakfu_server import health_policy

    result = []
    for row in rows:
        character = store.character(row["account_id"], row["id"], db)
        if character.get("dungeon_modulation") is not None and character.get(
            "mount_state", {}
        ).get("mounted", False):
            # An automatic sheet has no equipped mount. End riding while
            # preserving the owned mount unit, XP, health and saved gear.
            db.execute(
                "UPDATE character_mount_state SET mounted=false,revision=revision+1 "
                "WHERE character_id=%s AND mounted=true",
                (row["id"],),
            )
            from wakfu_server.mount_state import load as load_mount_state

            character["mount_state"] = load_mount_state(db, row["id"])
        # Dungeon entry/exit and authorized item XP can change the ordinary
        # build baseline. Reconcile retained eWO receipts before deriving the
        # world maximum so its raw PA never remains pinned to a stale level.
        from wakfu_server.equipment_hp_lifecycle import reconcile_selected_build

        reconcile_selected_build(db, character)
        character = store.character(row["account_id"], row["id"], db)
        maximum = effective_health_max(character)
        hp = health_policy.visible(
            maximum,
            character["hp_damage"],
            character["health_dead"],
            character.get("hp_zero_valid", False),
        )
        if (row["hp"], row["max_hp"]) != (hp, maximum):
            health_policy.reconfigure(db, character, maximum)
            now = store.now()
            # The regeneration trigger freezes the unchanged wound baseline.
            # Preserve its existing rate; dead characters cannot regenerate.
            db.execute(
                "INSERT INTO character_regeneration"
                "(character_id,initial_hp,started_at,last_at,coefficient) "
                "VALUES(%s,%s,%s,%s,0) ON CONFLICT(character_id) DO UPDATE SET "
                "initial_hp=excluded.initial_hp,started_at=excluded.started_at,"
                "last_at=excluded.last_at,coefficient=CASE WHEN excluded.initial_hp=0 "
                "THEN 0 ELSE character_regeneration.coefficient END",
                (row["id"], hp, now, now),
            )
        if character["health_dead"]:
            db.execute(
                "UPDATE character_regeneration SET coefficient=0 "
                "WHERE character_id=%s AND coefficient<>0",
                (row["id"],),
            )
        character.update(hp=hp, max_hp=maximum)
        result.append(character)
    return tuple(result)
