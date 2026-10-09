"""Rebind a persisted private dungeon member to its verified selected lease."""

from wakfu_server import player_parties


def resume_member(store, account_id, generation, character_id, instance_id):
    """Resume membership without trusting a client-provided destination.

    The worker calls this after selecting the owned character and before its
    initial native bootstrap. Old-generation outbox intent is superseded:
    bootstrap hydrates the already persisted location, never repeats travel.
    """
    if type(instance_id) is not int or instance_id <= 0:
        raise ValueError("Dungeon recovery requires a private instance")
    with store.connection() as db:
        player_parties._lock_members(db, [character_id])
        store.lock_character(db, account_id, generation, character_id)
        character = db.execute(
            "SELECT map_id,instance_id FROM characters WHERE id=%s AND account_id=%s",
            (character_id, account_id),
        ).fetchone()
        if character is None or character["instance_id"] != instance_id:
            raise ValueError("Dungeon recovery location is not authoritative")
        identity = db.execute(
            "SELECT party_id FROM dungeon_instances WHERE instance_id=%s",
            (instance_id,),
        ).fetchone()
        if identity is None:
            raise ValueError("Dungeon recovery run is absent")
        party = db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (identity["party_id"],),
        ).fetchone()
        run = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (instance_id,),
        ).fetchone()
        member = db.execute(
            "SELECT * FROM dungeon_instance_members WHERE instance_id=%s AND character_id=%s FOR UPDATE",
            (instance_id, character_id),
        ).fetchone()
        social_member = db.execute(
            "SELECT 1 FROM player_party_members WHERE party_id=%s AND character_id=%s",
            (identity["party_id"], character_id),
        ).fetchone()
        if (
            party is None
            or run["status"] != "active"
            or member is None
            or member["status"] != "active"
            or social_member is None
            or character["map_id"] != run["start_map_id"]
        ):
            raise ValueError("Dungeon recovery membership is not active")
        previous_generation = member["session_generation"]
        if previous_generation != generation:
            db.execute(
                "UPDATE dungeon_instance_members SET session_generation=%s "
                "WHERE instance_id=%s AND character_id=%s",
                (generation, instance_id, character_id),
            )
            db.execute(
                "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
                "WHERE instance_id=%s AND character_id=%s AND status='pending' "
                "AND session_generation<>%s",
                (store.now(), instance_id, character_id, generation),
            )
        return dict(
            instance_id=instance_id,
            party_id=run["party_id"],
            rebound=previous_generation != generation,
            previous_generation=previous_generation,
            generation=generation,
        )
