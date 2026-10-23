"""Owned World facade for environmental instances and durable delivery."""
from .environmental_runtime import integer
from . import environmental_presence as presence


def _inactive():
    return dict(
        instances=[],
        deliveries=[],
        inactive_scope=True,
        rewards=dict(delivered=[], capacity_pending=[], character=None),
    )


def _lock_owner(store, db, account_id, generation, character_id):
    """Match hero selection's account -> session -> character lock prefix."""
    if (
        db.execute(
            "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
        ).fetchone()
        is None
    ):
        raise ValueError("Missing environmental owner account")
    lease = db.execute(
        "SELECT character_id FROM sessions WHERE account_id=%s AND generation=%s "
        "AND expires_at>%s FOR UPDATE",
        (account_id, generation, store.now()),
    ).fetchone()
    if lease is None or lease["character_id"] != character_id:
        raise ValueError("Invalid environmental owner session")
    store.lock_character(db, account_id, generation, character_id)


def _clock(store, now_ms):
    value = int(store.now().timestamp() * 1000) if now_ms is None else now_ms
    return integer(value, "clock")


def _location(location):
    if type(location) is not dict:
        raise ValueError("Missing environmental location")
    result = dict(location)
    integer(result.get("map_id"), "map", minimum=1)
    integer(result.get("instance_id"), "world instance")
    if result.get("region_id") is not None:
        integer(result["region_id"], "region", minimum=1)
    return result


def refresh(
    store, account_id, generation, character_id, *, location, now_ms=None, groups=None
):
    """Resume/expire persisted instances and claim rewards under one owner lock."""
    from . import (
        environmental_storage,
        environmental_cleanup,
        environmental_company,
        environmental_resource_population,
    )

    location = _location(location)
    now_ms = _clock(store, now_ms)
    occupied = presence.capture(location["map_id"], location["instance_id"])
    if occupied is None:
        return _inactive()
    with store.connection() as db:
        _lock_owner(store, db, account_id, generation, character_id)
        if not presence.current(occupied, location["map_id"], location["instance_id"]):
            return _inactive()
        hero_ids = environmental_company.loaded_ids(db, account_id, character_id)
        for hero_id in sorted(hero_ids):
            store.lock_character(db, account_id, generation, hero_id, selected=False)
        if (
            db.execute(
                "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f ON f.id=p.fight_id "
                "WHERE p.account_id=%s AND p.character_id=ANY(%s) AND f.status IN ('placement','active') LIMIT 1",
                (account_id, [character_id, *hero_ids]),
            ).fetchone()
            is not None
        ):
            raise ValueError(
                "Environmental delivery requires an owned exploration scene"
            )
        snapshot = environmental_storage.refresh(
            db,
            account_id=account_id,
            character_id=character_id,
            location=location,
            now_ms=now_ms,
            groups=groups,
        )
        if snapshot.get("inactive_scope"):
            return _inactive()
        rewards = environmental_storage.claim_pending(
            db,
            store,
            account_id=account_id,
            character_id=character_id,
            now_ms=now_ms,
        )
        result = dict(snapshot, rewards=rewards)
        if rewards["delivered"]:
            # Include the newly committed claim's outbox in this same response.
            result.update(
                environmental_storage.refresh(
                    db,
                    account_id=account_id,
                    character_id=character_id,
                    location=location,
                    now_ms=now_ms,
                    groups=groups,
                )
            )
        result["hero_rewards"] = {}
        for hero_id in hero_ids:
            hero_snapshot = environmental_storage.refresh(
                db,
                account_id=account_id,
                character_id=hero_id,
                location=location,
                now_ms=now_ms,
                groups=groups,
            )
            if hero_snapshot.get("inactive_scope"):
                return _inactive()
            hero_rewards = environmental_storage.claim_pending(
                db, store, account_id=account_id, character_id=hero_id, now_ms=now_ms
            )
            if hero_rewards["delivered"]:
                hero_snapshot = environmental_storage.refresh(
                    db,
                    account_id=account_id,
                    character_id=hero_id,
                    location=location,
                    now_ms=now_ms,
                    groups=groups,
                )
            hero_claimed = [
                row for row in hero_snapshot["deliveries"] if row["kind"] == "claimed"
            ]
            if hero_claimed:
                # The connection uses the native owned-hero entity refresh;
                # selected-player inventory messages would replace the wrong bag.
                hero_claimed[0]["hero_character"] = store.character(
                    account_id, hero_id, db
                )
            result["hero_rewards"][hero_id] = hero_rewards
            result["deliveries"].extend(hero_snapshot["deliveries"])
        claimed = [row for row in result["deliveries"] if row["kind"] == "claimed"]
        if claimed:
            from wakfu_server.combat_lifecycle import outside_progression
            from wakfu_server.inventory_items import equipment_inventory
            from wakfu_server.inventory_move import synchronization
            from wakfu_server.exploration_secrets import account_packet
            from wakfu_server import companions
            from wakfu_server.wire import account_kamas_update

            main_claimed = [
                row for row in claimed if row["character_id"] == character_id
            ]
            wallet = db.execute(
                "SELECT kamas FROM account_wallets WHERE account_id=%s", (account_id,)
            ).fetchone()
            # Reconstruct absolute state even after a failed socket send. Never
            # replay additive XP notifications or inventory insert operations.
            if main_claimed:
                saved = store.character(account_id, character_id, db)
                # Match combat-drop delivery: 13078 hydrates the equipment
                # registry, while 13713 replaces the actual owned bag contents.
                # Rebuild from current state on retries, never replay 12470
                # quantity deltas or grant the reward a second time.
                main_claimed[0]["packets"] = [
                    outside_progression(saved),
                    synchronization(saved),
                    equipment_inventory(saved),
                ]
                result["character"] = saved
            claimed[0]["packets"].extend(
                [
                    (12753, account_kamas_update(wallet["kamas"])),
                    companions.refresh_packet(companions.collection(db, account_id)),
                    account_packet(db, account_id),
                ]
            )
        result["released_memberships"] = environmental_cleanup.release_memberships(
            db,
            map_id=location["map_id"],
            instance_id=location["instance_id"],
            now_ms=now_ms,
        )
        result["retired_resources"] = environmental_resource_population.cleanup(
            db,
            map_id=location["map_id"],
            instance_id=location["instance_id"],
            now_ms=now_ms,
        )
        result[
            "resource_publications"
        ] = environmental_resource_population.pending_publications(
            db,
            map_id=location["map_id"],
            instance_id=location["instance_id"],
            now_ms=now_ms,
        )
        if groups is not None:
            from .environmental_group_population import cleanup

            result["retired_groups"] = cleanup(
                db,
                map_id=location["map_id"],
                instance_id=location["instance_id"],
                now_ms=now_ms,
            )
        from .environmental_result_delivery import plan_result_delivery

        for delivery in result["deliveries"]:
            if delivery["kind"] != "completed":
                continue
            event = db.execute(
                "SELECT * FROM environmental_event_instances WHERE instance_id=%s",
                (delivery["instance_id"],),
            ).fetchone()
            participant = db.execute(
                "SELECT * FROM environmental_participants WHERE instance_id=%s AND character_id=%s",
                (delivery["instance_id"], delivery["character_id"]),
            ).fetchone()
            view = environmental_storage._view(
                db,
                event,
                environmental_storage._event_profile(db, event),
                participant,
                now_ms,
            )
            plan = plan_result_delivery(
                dict(delivery),
                view,
                account_id=account_id,
                character_id=delivery["character_id"],
            )
            if plan is not None:
                if delivery["character_id"] != character_id:
                    # Native result context belongs to the selected character.
                    # Preserve this outbox until its owner is selected, while
                    # separate claimed rows still refresh the loaded hero.
                    delivery["deferred_selected_result"] = True
                    continue
                from wakfu_server.wire import native_xp_rate_packet

                delivery["packets"].append(native_xp_rate_packet(view["xp_rate_bp"]))
                delivery["packets"].extend(plan["packets"])
                delivery["result_view"] = view
        return result


def acknowledge_resources(
    store,
    account_id,
    generation,
    character_id,
    *,
    location,
    publication_ids,
    now_ms=None
):
    from . import environmental_resource_population

    location = _location(location)
    if presence.capture(location["map_id"], location["instance_id"]) is None:
        return 0
    if type(publication_ids) not in (tuple, list) or any(
        type(i) is not int or i <= 0 for i in publication_ids
    ):
        raise ValueError("Invalid environmental resource publication acknowledgement")
    with store.connection() as db:
        _lock_owner(store, db, account_id, generation, character_id)
        return environmental_resource_population.acknowledge(
            db,
            map_id=location["map_id"],
            instance_id=location["instance_id"],
            publication_ids=publication_ids,
            now_ms=_clock(store, now_ms),
        )


def acknowledge(store, account_id, generation, character_id, delivery_keys):
    from . import environmental_storage, environmental_company

    if type(delivery_keys) not in (list, tuple) or any(
        type(key) is not str or not key or len(key) > 200 for key in delivery_keys
    ):
        raise ValueError("Invalid environmental delivery acknowledgement")
    with store.connection() as db:
        _lock_owner(store, db, account_id, generation, character_id)
        # Current selection may acknowledge only itself and its loaded heroes.
        # A removed hero keeps its undelivered outbox for later re-admission.
        return sum(
            environmental_storage.acknowledge(
                db,
                account_id=account_id,
                character_id=identity,
                delivery_keys=tuple(dict.fromkeys(delivery_keys)),
            )
            for identity in (
                character_id,
                *environmental_company.loaded_ids(db, account_id, character_id),
            )
        )
