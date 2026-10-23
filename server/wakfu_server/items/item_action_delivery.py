"""Deliver native item-action products inside the consuming transaction.

The caller authorizes and locks the owner, consumes the source, and commits or
rolls back the whole operation. Packets are returned for publication after commit.
"""
import struct


def validate_selections(products, selections_by_reference):
    """Validate explicit singleton output choices against original templates."""
    from .element_selection import _validate_selection

    if selections_by_reference is None:
        return {}
    if not isinstance(products, dict) or not isinstance(selections_by_reference, dict):
        raise ValueError("Invalid output elemental selections")
    result = {}
    for reference, selection in selections_by_reference.items():
        if (
            type(reference) is not int
            or type(products.get(reference)) is not int
            or products.get(reference) != 1
            or not isinstance(selection, dict)
            or set(selection) != {"damage_elements", "resistance_elements"}
        ):
            raise ValueError("Elemental output selection requires a singleton product")
        damage, resistance = (
            selection["damage_elements"],
            selection["resistance_elements"],
        )
        _validate_selection(reference, damage, resistance)
        if not (damage or resistance):
            raise ValueError("Explicit output elemental selection must be identified")
        result[reference] = dict(selection)
    return result


def grant_outputs(
    store,
    db,
    account_id,
    generation,
    character,
    products,
    *,
    force_bound=False,
    selections_by_reference=None,
    shards_by_reference=None,
    appearances_by_reference=None,
    observations_by_reference=None
):
    """Grant a server-resolved reference/quantity mapping without opening a transaction.

    Ordinary equipped bags share the existing acquisition placement policy.
    Specialized bags remain excluded until their native filters are supported.
    A capacity failure must roll back the caller's complete consumption action.
    """
    from wakfu_server import inventory_items, inventory_elements
    from wakfu_server.inventory_move import ACQUISITION_STACKS
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server import account_quest_inventory, quest_inventory
    from wakfu_server.achievements.rewards import _plan_item_capacity
    from wakfu_server.combat_drop_delivery import (
        _binding_rows,
        _container_can_hold,
        _effective_bound,
        _equipped_uids,
        _identified_uids,
        _item_proto,
        _save_binding,
        _template_bound,
    )

    if (
        type(force_bound) is not bool
        or not isinstance(products, dict)
        or not products
        or character.get("account_id") != account_id
        or type(character.get("id")) is not int
    ):
        raise ValueError("Invalid native item-action products or owner")
    for reference, quantity in products.items():
        if (
            type(reference) is not int
            or reference not in ACQUISITION_STACKS
            or type(quantity) is not int
            or not 1 <= quantity < (1 << 31)
        ):
            raise ValueError("Invalid native item-action product quantity")
        rule = ACQUISITION_STACKS[reference]
        if type(rule.get("maximum")) is not int or rule["maximum"] < 1:
            raise ValueError("Invalid native item-action acquisition stack")
    selections = validate_selections(products, selections_by_reference)
    shards = {} if shards_by_reference is None else shards_by_reference
    if not isinstance(shards, dict):
        raise ValueError("Invalid explicit output socket states")
    from .conversion_shard_policy import validate_target

    for reference, state in shards.items():
        if (
            type(reference) is not int
            or type(products.get(reference)) is not int
            or products[reference] != 1
        ):
            raise ValueError("Explicit output sockets require a singleton product")
        validate_target(db, reference, state)
    appearances = {} if appearances_by_reference is None else appearances_by_reference
    if not isinstance(appearances, dict):
        raise ValueError("Invalid explicit output appearances")
    from .conversion_appearance_policy import validate_target as validate_appearance

    for reference, appearance in appearances.items():
        if (
            type(reference) is not int
            or type(products.get(reference)) is not int
            or products[reference] != 1
        ):
            raise ValueError("Explicit output appearance requires a singleton product")
        validate_appearance(db, reference, reference, appearance)
    observations = (
        {} if observations_by_reference is None else observations_by_reference
    )
    if not isinstance(observations, dict):
        raise ValueError("Invalid explicit output recycling observations")
    from .conversion_observation_policy import validate_target as validate_observation

    for reference, observation in observations.items():
        if (
            type(reference) is not int
            or type(products.get(reference)) is not int
            or products[reference] != 1
        ):
            raise ValueError("Explicit output observations require a singleton product")
        validate_observation(reference, observation)

    character_id = character["id"]
    # Reload after source consumption: its freed position may hold the reward.
    lock_inventory_character(store, db, account_id, generation, character_id)
    containers = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM inventory_containers WHERE character_id=%s "
            "ORDER BY kind,uid FOR UPDATE",
            (character_id,),
        ).fetchall()
    ]
    eligible = [bag for bag in containers if _container_can_hold(bag, character_id)]
    items = inventory_items.load(db, character_id)
    bindings = _binding_rows(db, items)
    excluded = _equipped_uids(store, account_id, character_id, db)
    excluded.update(_identified_uids(db, items))
    excluded.update(
        row["uid"]
        for row in db.execute(
            "SELECT i.uid FROM player_exchange_items i "
            "JOIN player_exchanges e ON e.id=i.exchange_id "
            "WHERE i.character_id=%s AND e.state IN ('invitation','active')",
            (character_id,),
        )
    )
    uids = [item["uid"] for item in items]
    if uids:
        excluded.update(
            row["uid"]
            for row in db.execute(
                "SELECT uid FROM inventory_item_recycling_state WHERE uid=ANY(%s)",
                (uids,),
            )
        )
    for item in items:
        item["bound"] = bindings.get(item["uid"], False)
    eligible_ids = {bag["uid"] for bag in eligible}
    packets = []
    for reference, quantity in sorted(products.items()):
        if reference in account_quest_inventory.REFERENCES | quest_inventory.REFERENCES:
            # These inventories do not consume physical bag positions.
            remaining = quantity
            while remaining:
                amount = min(remaining, 32767)
                result = inventory_items.grant(
                    store,
                    account_id,
                    generation,
                    character_id,
                    reference=reference,
                    quantity=amount,
                    container=0,
                    slot=0,
                    allowed_references=ACQUISITION_STACKS,
                    db=db,
                )
                packets.append(inventory_items.insertion(result, notification=True))
                remaining -= amount
            continue

        rule = ACQUISITION_STACKS[reference]
        is_mount = (
            db.execute(
                "SELECT model_id FROM mount_models WHERE reference=%s", (reference,)
            ).fetchone()
            is not None
        )
        is_pet = (
            db.execute(
                "SELECT model_id FROM native_pet_models WHERE reference=%s",
                (reference,),
            ).fetchone()
            is not None
        )
        explicit_selection = selections.get(reference)
        explicit_shards = shards.get(reference)
        explicit_appearance = appearances.get(reference)
        explicit_observation = observations.get(reference)
        maximum = (
            1
            if is_mount
            or is_pet
            or explicit_selection is not None
            or explicit_shards is not None
            or explicit_appearance is not None
            or explicit_observation is not None
            else min(rule["maximum"], 32767)
        )
        selection = (
            inventory_elements.create(reference)
            if explicit_selection is None
            else explicit_selection
        )
        selected_masks = (
            None if selection is None else inventory_elements.masks(selection)
        )
        bound = _template_bound(reference) or force_bound
        compatible = [
            item
            for item in items
            if explicit_selection is None
            and explicit_shards is None
            and explicit_appearance is None
            and explicit_observation is None
            and not is_mount
            and not is_pet
            and rule["minimal_mergeable"]
            and item["reference"] == reference
            and item["container"] in eligible_ids
            and item["uid"] not in excluded
            and "mount" not in item
            and "pet" not in item
            and _effective_bound(item) == bound
            and inventory_elements.masks(item) == selected_masks
        ]
        merges, placements = _plan_item_capacity(
            eligible, items, compatible, quantity, maximum
        )
        for item, amount in merges:
            db.execute(
                "UPDATE inventory_items SET quantity=quantity+%s WHERE uid=%s "
                "AND character_id=%s",
                (amount, item["uid"], character_id),
            )
            item["quantity"] += amount
            packets.append((12470, struct.pack(">qh", item["uid"], amount)))
        for bag, slot, amount in placements:
            item = inventory_items.grant(
                store,
                account_id,
                generation,
                character_id,
                reference=reference,
                quantity=amount,
                container=bag["uid"],
                slot=slot,
                allowed_references=ACQUISITION_STACKS,
                db=db,
            )
            _save_binding(db, item["uid"], reference, bound)
            if explicit_selection is not None:
                saved = db.execute(
                    "UPDATE inventory_item_elements SET damage_elements=%s,resistance_elements=%s "
                    "WHERE uid=%s RETURNING uid",
                    (
                        selection["damage_elements"],
                        selection["resistance_elements"],
                        item["uid"],
                    ),
                ).fetchone()
                if saved is None:
                    raise ValueError("Missing typed output elemental selection state")
                item.update(selection)
            if explicit_shards is not None:
                from .inventory_shards import save

                save(db, item["uid"], explicit_shards)
                item["shard_state"] = explicit_shards
            if explicit_appearance is not None:
                db.execute(
                    "INSERT INTO inventory_item_appearances(uid,appearance_ref) VALUES(%s,%s)",
                    (item["uid"], explicit_appearance),
                )
                item["appearance_ref"] = explicit_appearance
            if explicit_observation is not None:
                db.execute(
                    "INSERT INTO inventory_item_recycling_state(uid,unidentified,socketed) VALUES(%s,%s,%s)",
                    (
                        item["uid"],
                        explicit_observation["unidentified"],
                        explicit_observation["socketed"],
                    ),
                )
            item["bound"] = bound
            items.append(item)
            proto = _item_proto(item)
            packets.append(
                (
                    12471,
                    struct.pack(">qhI", item["container"], item["slot"], len(proto))
                    + proto
                    + b"\x01",
                )
            )
    return dict(
        character=store.character(account_id, character_id, db),
        packets=packets,
    )
