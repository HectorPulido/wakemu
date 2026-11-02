"""Lease a native signed-short topology identity for an admitted encounter."""


def valid(value):
    return type(value) is int and 1 <= value <= 32767


def reserve(db, *, fight_id, map_id, preferred):
    """Keep world/actor identities intact; serialize allocation per native map.

    The placement caller holds its fight and owner locks. Its committed layout
    is the durable lease and the fight's existing terminal status releases it.
    All new layouts take this lock, including those with a small preferred ID,
    so PvE, duel and concurrent server processes cannot choose the same slot.
    """
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("wakemu.combat-topology:" + str(map_id),),
    )
    rows = db.execute(
        "SELECT p.layout->'wire_instance_id' AS wire_id "
        "FROM fight_placement_layouts p JOIN combat_fights f ON f.id=p.fight_id "
        "WHERE p.map_id=%s AND p.fight_id<>%s "
        "AND f.status IN ('placement','active')",
        (map_id, fight_id),
    ).fetchall()
    used = {row["wire_id"] for row in rows if valid(row["wire_id"])}
    if valid(preferred) and preferred not in used:
        return preferred
    for candidate in range(1, 32768):
        if candidate not in used:
            return candidate
    raise ValueError("Native map has no free combat topology identity")
