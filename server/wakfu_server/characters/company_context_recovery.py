"""Retire private membership left behind by a completed public return."""


def reconcile_public_dungeon_memberships(db, account_id):
    """Keep valid private companies and combat frozen; repair public occupants.

    Selection owns the account/session lock. Only current, nondeleted owned
    characters already persisted in the public world qualify. No movement,
    inventory, reward or live combat state is inferred or changed here.
    """
    repaired = db.execute(
        "UPDATE dungeon_instance_members m SET status='returned',ended_at=CURRENT_TIMESTAMP "
        "FROM characters c WHERE c.id=m.character_id AND c.account_id=%s "
        "AND c.deleted_at IS NULL AND c.instance_id=0 AND m.status='active' "
        "AND NOT EXISTS(SELECT 1 FROM combat_fight_participants p "
        "JOIN combat_fights f ON f.id=p.fight_id WHERE p.character_id=c.id "
        "AND f.status IN ('placement','active')) "
        "RETURNING m.instance_id,m.character_id",
        (account_id,),
    ).fetchall()
    for row in repaired:
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=CURRENT_TIMESTAMP "
            "WHERE instance_id=%s AND character_id=%s AND status='pending'",
            (row["instance_id"], row["character_id"]),
        )
    return tuple(row["character_id"] for row in repaired)
