"""Rebind a persisted private dungeon member to its verified selected lease."""

from wakfu_server import player_parties


def resume_member(
    store, account_id, generation, character_id, instance_id, *, in_fight=None
):
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
        owned_ids = _owned_cohort(db, account_id, instance_id, character_id)
        fight_states = [
            in_fight(identity) if in_fight is not None else False
            for identity in owned_ids
        ]
        if any(type(state) is not bool for state in fight_states):
            raise ValueError("Dungeon recovery combat state must be boolean")
        fighting = any(fight_states)
        if (
            party is None
            or run["status"] != "active"
            or member is None
            or member["status"] != "active"
            or (social_member is None and not fighting)
            or character["map_id"] != run["start_map_id"]
        ):
            if fighting:
                raise ValueError(
                    "Cannot recover an invalid dungeon location during combat"
                )
            return _recover_exterior(
                store,
                db,
                account_id,
                generation,
                character_id,
                character,
                run,
                character_ids=owned_ids,
            )
        previous_generation = member["session_generation"]
        db.execute(
            "UPDATE dungeon_instance_members SET session_generation=%s "
            "WHERE instance_id=%s AND character_id=ANY(%s) AND status='active'",
            (generation, instance_id, list(owned_ids)),
        )
        db.execute(
            "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
            "WHERE instance_id=%s AND character_id=ANY(%s) AND status='pending' "
            "AND session_generation<>%s",
            (store.now(), instance_id, list(owned_ids), generation),
        )
        if not fighting:
            from wakfu_server.characters.dungeon_modulation_health import reconcile

            reconcile(store, db, owned_ids)
        return dict(
            instance_id=instance_id,
            character_ids=owned_ids,
            party_id=run["party_id"],
            rebound=previous_generation != generation,
            previous_generation=previous_generation,
            generation=generation,
        )


def _owned_cohort(db, account_id, instance_id, character_id):
    """Only durable same-account members at this actual private location."""
    rows = db.execute(
        "SELECT c.id FROM characters c JOIN dungeon_instance_members m "
        "ON m.character_id=c.id AND m.instance_id=c.instance_id "
        "WHERE c.account_id=%s AND c.instance_id=%s AND c.deleted_at IS NULL "
        "AND m.status='active' ORDER BY c.id FOR UPDATE OF c",
        (account_id, instance_id),
    ).fetchall()
    return tuple(sorted({character_id, *(row["id"] for row in rows)}))


def _recover_exterior(
    store, db, account_id, generation, character_id, character, run, *, character_ids
):
    """Repair persisted private locations using pinned server-owned exit facts."""
    from wakfu_server import dungeon_runtime
    from wakfu_server.maps.dungeon_exit import automatic_destination

    _, configuration = dungeon_runtime.configuration_for_instance(
        db, run["instance_id"]
    )
    destination = automatic_destination(character, run, configuration)
    db.execute(
        "UPDATE characters SET map_id=%s,instance_id=0,x=%s,y=%s,z=%s "
        "WHERE id=ANY(%s) AND account_id=%s AND instance_id=%s",
        (
            destination["map_id"],
            destination["x"],
            destination["y"],
            destination["z"],
            list(character_ids),
            account_id,
            run["instance_id"],
        ),
    )
    db.execute(
        "UPDATE dungeon_instance_members SET status='returned',ended_at=%s "
        "WHERE instance_id=%s AND character_id=ANY(%s) AND status='active'",
        (store.now(), run["instance_id"], list(character_ids)),
    )
    db.execute(
        "UPDATE dungeon_transition_outbox SET status='superseded',superseded_at=%s "
        "WHERE character_id=ANY(%s) AND status='pending'",
        (store.now(), list(character_ids)),
    )
    db.execute(
        "UPDATE dungeon_instances SET status='closed',ended_at=%s WHERE instance_id=%s "
        "AND status IN ('active','completed') AND NOT EXISTS "
        "(SELECT 1 FROM dungeon_instance_members WHERE instance_id=%s AND status='active')",
        (store.now(), run["instance_id"], run["instance_id"]),
    )
    from wakfu_server.characters.dungeon_modulation_health import reconcile

    reconcile(store, db, character_ids)
    return dict(
        instance_id=0,
        party_id=run["party_id"],
        rebound=False,
        generation=generation,
        recovered_exterior=True,
        character_ids=character_ids,
        destination=destination,
    )
