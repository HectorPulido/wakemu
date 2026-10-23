"""Fenced exploration/session checkpoints for owned company consumable clocks."""


def company_membership(store, db, account_id, generation, previous, current):
    """Checkpoint clocks inside the transaction changing active company members.

    The caller owns the account, session and roster locks. Characters leaving
    the company stop their online clock; newly active characters resume without
    charging the inactive interval. Shared members keep their existing anchor.
    """
    from wakfu_server import consumable_buffs
    from wakfu_server.consumable_characteristics import reconcile_health

    previous, current = set(previous), set(current)
    for identity in sorted(previous ^ current):
        store.lock_character(db, account_id, generation, identity, selected=False)
        if (
            db.execute(
                "SELECT 1 FROM character_consumable_buffs WHERE character_id=%s LIMIT 1",
                (identity,),
            ).fetchone()
            is None
        ):
            continue
        if identity in current:
            states = consumable_buffs.resume(store, db, identity, generation)
        else:
            states = consumable_buffs.pause(store, db, identity, generation)
        character = store.character(account_id, identity, db)
        character["consumable_states"] = states
        reconcile_health(db, character)


def clear_for_test(store, account_id, generation, character):
    """Clear only the selected administrator's food states for local probes."""
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.consumable_characteristics import reconcile_health

    with store.connection() as db:
        admin = db.execute(
            "SELECT is_admin FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
        ).fetchone()
        if not admin or not admin["is_admin"]:
            raise PermissionError("Este comando requiere una cuenta administradora")
        lock_inventory_character(store, db, account_id, generation, character["id"])
        _idle(db, character["id"], store.now())
        db.execute(
            "DELETE FROM character_consumable_buffs WHERE character_id=%s",
            (character["id"],),
        )
        saved = reconcile_health(db, store.character(account_id, character["id"], db))
    updated = dict(character, consumable_states=())
    updated.update(
        {key: saved[key] for key in ("hp", "max_hp", "hp_damage", "health_dead")}
    )
    return updated


def synchronize(
    store,
    account_id,
    generation,
    character,
    *,
    mode="tick",
    in_combat=False,
    company_updates=None
):
    """Checkpoint the selected main and active heroes under one real lease.

    Only company members carrying durable states are touched. Hero hydration is
    needed only when retirement changes effective health. The returned snapshot
    belongs solely to the supplied character and preserves its live location.
    An optional list receives changed hero snapshots only after SQL commits.
    """
    from wakfu_server import consumable_buffs
    from wakfu_server.consumable_characteristics import reconcile_health
    from wakfu_server.inventory_owner import lock_inventory_character

    if mode not in ("resume", "tick", "pause") or type(in_combat) is not bool:
        raise ValueError("Invalid consumable session lifecycle")
    if company_updates is not None and not isinstance(company_updates, list):
        raise ValueError("Consumable company updates require a list")
    committed_updates = []
    with store.connection() as db:
        session = db.execute(
            "SELECT generation,character_id FROM sessions WHERE account_id=%s AND generation=%s AND expires_at>%s FOR UPDATE",
            (account_id, generation, store.now()),
        ).fetchone()
        if session is None:
            return character
        # Do not rely on the main's cached state list: a hero may be the only
        # company member with an online consumable. This is a bounded indexed
        # probe, not full character/roster hydration on every world frame.
        rows = db.execute(
            "SELECT b.* FROM character_consumable_buffs b "
            "JOIN characters c ON c.id=b.character_id "
            "WHERE c.account_id=%s AND c.deleted_at IS NULL AND "
            "(c.id=%s OR EXISTS(SELECT 1 FROM account_hero_slots h "
            "JOIN account_hero_rosters r USING(account_id) "
            "WHERE h.account_id=%s AND h.character_id=c.id AND r.leader_id=%s)) "
            "ORDER BY b.character_id,b.uid",
            (account_id, session["character_id"], account_id, session["character_id"]),
        ).fetchall()
        before = {}
        before_states = {}
        for row in rows:
            before.setdefault(row["character_id"], set()).add(
                (row["uid"], row["level"])
            )
            if company_updates is not None:
                before_states.setdefault(row["character_id"], []).append(
                    consumable_buffs._public(row)
                )
        owners = set(before)
        # A previously published state can have been retired by another owned
        # boundary; clear that stale cache and reconcile the main's maximum.
        if character.get("consumable_states"):
            owners.add(character["id"])
        if not owners:
            return character
        updated = dict(character)
        for owner_id in sorted(owners):
            lock_inventory_character(store, db, account_id, generation, owner_id)
            if mode == "resume":
                states = consumable_buffs.resume(store, db, owner_id, generation)
            elif mode == "pause":
                states = consumable_buffs.pause(store, db, owner_id, generation)
            else:
                states = consumable_buffs.active_states(
                    store, db, owner_id, generation=generation
                )
            previous = before.get(owner_id, set())
            if owner_id == character["id"]:
                previous = {
                    (state["uid"], state["level"])
                    for state in character.get("consumable_states", ())
                }
                updated["consumable_states"] = states
            changed = previous != {(state["uid"], state["level"]) for state in states}
            if changed and not in_combat:
                saved = store.character(account_id, owner_id, db)
                saved["consumable_states"] = states
                saved = reconcile_health(db, saved)
                if owner_id == character["id"]:
                    updated.update(
                        {
                            key: saved[key]
                            for key in ("hp", "max_hp", "hp_damage", "health_dead")
                        }
                    )
                elif company_updates is not None:
                    committed_updates.append(
                        (
                            dict(
                                saved,
                                consumable_states=tuple(
                                    before_states.get(owner_id, ())
                                ),
                            ),
                            saved,
                        )
                    )
    if company_updates is not None:
        company_updates.extend(committed_updates)
    return updated
