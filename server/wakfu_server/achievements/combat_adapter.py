"""Post-group adapters for durable combat achievement settlement."""

from . import service


def settle_participants(
    db, store, fight, participants, original_monsters, *, environmental_scene=None
):
    """Return private packets and exact outbox receipts inside settlement.

    Participants and original monsters must come from the durable settlement
    roster and original encounter constructor. The caller invokes this after
    group/dungeon settlement. Rift facts come from all durable admitted waves;
    the current wave roster cannot stand in for all original defeated actors.
    """
    if (
        fight.phase != "finished"
        or type(fight.winner) is not int
        or fight.winner not in (0, 1)
    ):
        raise ValueError("Achievement adapter requires a resolved fight")
    is_rift = getattr(fight, "rift_wave_state", None) is not None
    original_monsters = tuple(original_monsters)
    registrations = getattr(fight, "native_summon_registrations", {})
    killed = []
    identities = set()
    for monster in () if is_rift else original_monsters:
        identity, breed = monster["id"], monster["ref"]
        if (
            type(identity) is not int
            or identity in identities
            or type(breed) is not int
            or breed <= 0
        ):
            raise ValueError("Invalid original achievement encounter roster")
        identities.add(identity)
        actor = fight.actors.get(identity)
        if actor is None:
            raise ValueError("Original achievement monster is missing")
        if (
            identity in registrations
            or actor.controlled
            or actor.team == fight.winner
            or actor.hp > 0
        ):
            continue
        killed.append({"id": identity, "ref": breed})
    by_owner = {}
    receipts = []
    custom_task_updates = []
    environmental_updates = []
    environmental_facts = []
    seen = set()
    eligible = []
    for member in participants:
        owner, identity = member["account_id"], member["character_id"]
        if (
            type(owner) is not int
            or owner <= 0
            or type(identity) is not int
            or identity <= 0
            or identity in seen
        ):
            raise ValueError("Invalid durable achievement participant")
        seen.add(identity)
        actor = fight.actors.get(identity)
        if actor is None:
            raise ValueError("Durable achievement participant is missing")
        if (
            member.get("withdrawn", False)
            or getattr(actor, "pve_withdrawn", False)
            or actor.team != fight.winner
        ):
            continue
        eligible.append((owner, identity))
    eligible_ids = tuple(identity for _, identity in eligible)
    for owner, identity in eligible:
        character = store.character(owner, identity, db)
        facts = killed
        if is_rift:
            from .rift_facts import load_locked

            facts = load_locked(db, fight, character, eligible_ids)
        result = service.settle(db, store, character, fight, facts)
        if "replay" in result and not is_rift:
            from . import scoped_combat_missions

            if not result["replay"] and environmental_scene is not None:
                try:
                    with db.transaction():
                        scoped_combat_missions.stage(
                            db,
                            store,
                            character,
                            fight,
                            original_monsters,
                            facts,
                            environmental_scene,
                            fresh=True,
                        )
                except Exception:
                    import logging

                    logging.getLogger(__name__).exception(
                        "Regional mission capture failed for character %s fight %s",
                        character["id"],
                        fight.id,
                    )
            # Pending work was frozen with its original assignment and victory.
            # Retry processing independently; replay never captures a new job.
            try:
                with db.transaction():
                    scoped_packets = scoped_combat_missions.process(
                        db, store, character, fight.id
                    )
            except Exception:
                import logging

                logging.getLogger(__name__).exception(
                    "Regional mission settlement failed for character %s fight %s",
                    character["id"],
                    fight.id,
                )
            else:
                result["packets"].extend(scoped_packets)
        from . import source_quest_encounters

        result["packets"].extend(
            source_quest_encounters.settle(
                db, store, character, fight, original_monsters
            )
        )
        from . import owned_quest_encounters

        result["packets"].extend(
            owned_quest_encounters.settle(
                db, store, character, fight, original_monsters
            )
        )
        from wakfu_server import owned_story_controller

        result["packets"].extend(
            owned_story_controller.settle_combat(
                db, store, character, fight, original_monsters
            )
        )
        from wakfu_server.custom_tasks.adapters import original_kills

        custom_result = original_kills(db, owner, identity, fight.id)
        if environmental_scene is not None and not is_rift:
            from wakfu_server.objectives.environmental_gameplay import settled_fight

            environmental_updates.extend(
                settled_fight(
                    db,
                    account_id=owner,
                    character_id=identity,
                    fight_id=fight.id,
                    source_scene=dict(
                        environmental_scene,
                        region_id=(
                            environmental_scene["admission_regions"].get(owner)
                            if "admission_regions" in environmental_scene
                            else environmental_scene.get("region_id")
                        ),
                        original_entities=tuple(
                            dict(monster) for monster in original_monsters
                        ),
                    ),
                    deferred_facts=environmental_facts,
                )
            )
        if custom_result["updated"] or custom_result["completed"]:
            custom_task_updates.append(
                {
                    "account_id": owner,
                    "character_id": identity,
                    "result": custom_result,
                }
            )
        from . import mission_character_events

        result["packets"].extend(
            mission_character_events.after_combat(db, store, character, fight.id)
        )
        by_owner.setdefault(owner, []).extend(result["packets"])
        key = result.get("notification_key")
        if key is not None:
            receipts.append({"account_id": owner, "character_id": identity, "key": key})
    if getattr(fight, "native_order_trial", None) is not None:
        from . import native_order_trial_settlement

        for owner, packets in native_order_trial_settlement.stage(
            db, store, fight, native_order_trial_settlement.load_rule()
        ).items():
            by_owner.setdefault(owner, []).extend(packets)
    if getattr(fight, "native_dj_dance", None) is not None:
        from wakfu_server import combat_native_dj_dance

        for owner, packets in combat_native_dj_dance.stage(db, store, fight).items():
            by_owner.setdefault(owner, []).extend(packets)
    from wakfu_server import owned_story_terminal_returns

    terminal_packets = owned_story_terminal_returns.stage(
        db, store, fight, participants, original_monsters
    )
    for owner, packets in (terminal_packets or {}).items():
        by_owner.setdefault(owner, []).extend(packets)
    if environmental_facts:
        from wakfu_server.objectives.environmental_gameplay import consume

        environmental_updates.extend(consume(db, environmental_facts))
    # The transport acknowledges only these exact keys after successful writes.
    # Reading all pending keys after publication could consume a newer event.
    delivery = {
        "packets_by_owner": by_owner,
        "notification_receipts": receipts,
        "custom_task_updates": custom_task_updates,
    }
    if environmental_scene is not None:
        delivery["environmental_updates"] = tuple(environmental_updates)
    return delivery
