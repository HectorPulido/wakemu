"""Authorized console relocation completes an owned dungeon departure atomically."""


def relocate(
    store, account_id, generation, character_id, source, destination, *, positions=None
):
    """Preserve normal map CAS while ending only this company's source run.

    Command authorization belongs to the console caller. This helper proves
    selected ownership, location, membership and absence of active combat again
    inside the same transaction as the move. It grants no dungeon rewards.
    """
    # Public maps, bags, ranches and rifts retain their existing caller-owned
    # lifecycle. Do not acquire a dungeon movement barrier for those contexts.
    known_dungeon = False
    if source.get("instance_id", 0) > 0:
        with store.connection() as db:
            known_dungeon = (
                db.execute(
                    "SELECT 1 FROM dungeon_instances WHERE instance_id=%s",
                    (source["instance_id"],),
                ).fetchone()
                is not None
            )
    if not known_dungeon:
        return store.transition_map(
            account_id, generation, character_id, source, destination
        )
    # The lookup connection is closed before entering a barrier or opening the
    # transaction. The source run is checked again under its actual locks.
    if positions is not None:
        from .dungeon_position_barrier import run_account_exit

        return run_account_exit(
            store,
            positions,
            account_id,
            transition=lambda: _relocate_dungeon(
                store, account_id, generation, character_id, source, destination
            ),
        )
    return _relocate_dungeon(
        store, account_id, generation, character_id, source, destination
    )


def _relocate_dungeon(store, account_id, generation, character_id, source, destination):
    if destination.get("instance_id") != 0:
        raise ValueError("Console relocation requires an exterior destination")
    from wakfu_server import player_parties
    from wakfu_server.characters.heroes import _outside_combat

    with store.connection() as db:
        identity = db.execute(
            "SELECT party_id FROM dungeon_instances WHERE instance_id=%s",
            (source.get("instance_id"),),
        ).fetchone()
        if identity is None:
            raise ValueError("Console relocation source dungeon disappeared")
        snapshot = db.execute(
            "SELECT h.character_id FROM account_hero_slots h "
            "JOIN account_hero_rosters r USING(account_id) "
            "WHERE h.account_id=%s AND r.leader_id=%s ORDER BY h.character_id",
            (account_id, character_id),
        ).fetchall()
        cohort = sorted({character_id, *(row["character_id"] for row in snapshot)})
        player_parties._lock_members(db, cohort)
        db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,))
        db.execute(
            "SELECT account_id FROM sessions WHERE account_id=%s FOR UPDATE",
            (account_id,),
        )
        roster = db.execute(
            "SELECT leader_id FROM account_hero_rosters WHERE account_id=%s FOR UPDATE",
            (account_id,),
        ).fetchone()
        slots = db.execute(
            "SELECT character_id FROM account_hero_slots WHERE account_id=%s ORDER BY character_id FOR UPDATE",
            (account_id,),
        ).fetchall()
        if (roster is not None and roster["leader_id"] != character_id) or sorted(
            {character_id, *(row["character_id"] for row in slots)}
        ) != cohort:
            raise ValueError("Console relocation company changed")
        for member_id in cohort:
            store.lock_character(
                db,
                account_id,
                generation,
                member_id,
                selected=member_id == character_id,
            )
        rows = db.execute(
            "SELECT id,map_id,instance_id FROM characters WHERE id=ANY(%s) ORDER BY id",
            (cohort,),
        ).fetchall()
        if any(
            row["map_id"] != source.get("map_id")
            or row["instance_id"] != source.get("instance_id")
            for row in rows
        ):
            raise ValueError("Console relocation company location changed")
        _outside_combat(db, cohort)
        if db.execute(
            "SELECT 1 FROM rift_instances WHERE status IN('entered','running') "
            "AND EXISTS(SELECT 1 FROM jsonb_array_elements_text(members) m WHERE m::bigint=ANY(%s)) LIMIT 1",
            (cohort,),
        ).fetchone():
            raise ValueError("Console dungeon departure conflicts with an active rift")
        db.execute(
            "SELECT id FROM player_parties WHERE id=%s FOR UPDATE",
            (identity["party_id"],),
        )
        run = db.execute(
            "SELECT * FROM dungeon_instances WHERE instance_id=%s FOR UPDATE",
            (source["instance_id"],),
        ).fetchone()
        members = db.execute(
            "SELECT character_id,status,session_generation FROM dungeon_instance_members "
            "WHERE instance_id=%s AND character_id=ANY(%s) ORDER BY character_id FOR UPDATE",
            (source["instance_id"], cohort),
        ).fetchall()
        if (
            run["party_id"] != identity["party_id"]
            or run["status"] not in ("active", "completed")
            or [row["character_id"] for row in members] != cohort
            or any(
                row["status"] != "active" or row["session_generation"] != generation
                for row in members
            )
        ):
            raise ValueError(
                "Console relocation has no current owned dungeon membership"
            )
        if db.execute(
            "SELECT 1 FROM dungeon_instance_members WHERE character_id=ANY(%s) "
            "AND instance_id<>%s AND status='active' LIMIT 1",
            (cohort, source["instance_id"]),
        ).fetchone():
            raise ValueError("Console relocation conflicts with another dungeon")
        now = store.now()
        db.execute(
            "UPDATE dungeon_instance_members SET status='returned',ended_at=%s "
            "WHERE instance_id=%s AND character_id=ANY(%s) AND status='active'",
            (now, source["instance_id"], cohort),
        )
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
            "WHERE instance_id=%s AND character_id=ANY(%s) AND status='pending'",
            (now, source["instance_id"], cohort),
        )
        store.transition_map_in_transaction(
            db, account_id, generation, character_id, source, destination
        )
        from wakfu_server.characters.dungeon_modulation_health import reconcile

        reconcile(store, db, cohort)
        db.execute(
            "UPDATE dungeon_instances SET revision=revision+1,"
            "status=CASE WHEN EXISTS(SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND status='active') THEN status ELSE 'closed' END,"
            "ended_at=CASE WHEN EXISTS(SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND status='active') THEN ended_at ELSE %s END "
            "WHERE instance_id=%s",
            (source["instance_id"], source["instance_id"], now, source["instance_id"]),
        )
        player_parties.cleanup_dungeon_solo(db, run["party_id"])
        return store.character(account_id, character_id, db)
