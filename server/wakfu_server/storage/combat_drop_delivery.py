"""Durable placement of accepted combat drops in bags or temporary inventory.

Call ``apply`` in the same PostgreSQL transaction as reward_policy/combat_drops.
Successful decisions are never rerolled here: their attempt identity is the
foreign key of the delivery receipt, and any failure rolls the whole victory
transaction back.
"""
import struct
from hashlib import sha256

from psycopg.pq import TransactionStatus

from wakfu_server.inventory_move import ACQUISITION_STACKS as STACKS


def _identified_uids(db, items):
    """Per-unit state must never be inherited by newly acquired plain units."""
    uids = [item["uid"] for item in items]
    if not uids:
        return set()
    return {
        row["uid"]
        for row in db.execute(
            "SELECT uid FROM inventory_item_shards WHERE uid=ANY(%s) "
            "UNION SELECT uid FROM inventory_item_appearances WHERE uid=ANY(%s) "
            "UNION SELECT uid FROM inventory_item_companions WHERE uid=ANY(%s) "
            "UNION SELECT source_uid AS uid FROM random_item_use_counters "
            "WHERE source_uid=ANY(%s)",
            (uids, uids, uids, uids),
        )
    }


def _integer(value, name, minimum=0, maximum=(1 << 63) - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"Invalid {name}")
    return value


def _item_proto(item):
    from wakfu_server.inventory_items import item_proto

    item = dict(item)
    if item.get("damage_elements") is None and item.get("resistance_elements") is None:
        item.pop("damage_elements", None)
        item.pop("resistance_elements", None)
    # All publication routes share the native field55 message codec.
    enum, binding_type, _ = _template_binding(item["reference"])
    if enum != "NOT_BOUND" or _effective_bound(item):
        item["binding_type"] = binding_type
        item["bound"] = _effective_bound(item)
    return item_proto(item)


def _template_bound(reference):
    return _template_binding(reference)[2]


def _template_binding(reference):
    from wakfu_server.exchange_rules import ITEMS

    row = ITEMS.get(str(reference))
    if row is None or row.get("reference") != reference:
        raise ValueError("Unknown native item binding template")
    binding = row.get("binding_template")
    if (
        not isinstance(binding, dict)
        or type(binding.get("default_eKo")) is not bool
        or type(binding.get("id")) is not int
        or binding.get("enum")
        not in (
            "NOT_BOUND",
            "BOUND_ON_EQUIP_TO_CHARACTER",
            "BOUND_ON_PICKUP_TO_CHARACTER",
            "BOUND_ON_EQUIP_TO_ACCOUNT",
            "BOUND_ON_PICKUP_TO_ACCOUNT",
        )
    ):
        raise ValueError("Incomplete native item binding template")
    return binding["enum"], binding["id"], binding["default_eKo"]


def _effective_bound(item):
    value = item.get("bound", False)
    if type(value) is not bool:
        raise ValueError("Invalid persisted item binding")
    return value or _template_bound(item["reference"])


def _binding_rows(db, items):
    if not items:
        return {}
    rows = db.execute(
        "SELECT uid,bound,template_reference FROM inventory_item_bindings WHERE uid=ANY(%s)",
        ([item["uid"] for item in items],),
    ).fetchall()
    result = {}
    references = {item["uid"]: item["reference"] for item in items}
    for row in rows:
        if type(row["bound"]) is not bool or row[
            "template_reference"
        ] != references.get(row["uid"]):
            raise ValueError("Invalid persisted item binding")
        result[row["uid"]] = row["bound"]
    return result


def _container_can_hold(container, character_id):
    """Return false for unsupported native filtered bags; reject corrupt rows."""
    if container.get("character_id") != character_id:
        raise ValueError("Foreign inventory container")
    if container.get("flags") != 0 or type(container.get("capacity")) is not int:
        raise ValueError("Invalid inventory container metadata")
    kind = container.get("kind")
    if kind == 0:
        if (
            container.get("reference") != 2175
            or container["capacity"] != 30
            or not 0 < container.get("uid", 0) < (1 << 63)
        ):
            raise ValueError("Invalid base inventory container")
        return True
    if kind not in (1, 2, 3) or not 0 < container.get("uid", 0) < (1 << 63):
        raise ValueError("Invalid inventory bag identity")
    from wakfu_server.inventory_bag_rules import RULES

    rule = RULES.get(container.get("reference"))
    if rule is None:
        raise ValueError("Unknown native inventory bag")
    if (
        rule.get("accepted_types")
        or rule.get("has_equip_criteria")
        or rule.get("capacity") != container["capacity"]
    ):
        return False
    return True


def _save_binding(db, uid, reference, bound):
    if bound:
        db.execute(
            "INSERT INTO inventory_item_bindings(uid,bound,template_reference) VALUES(%s,true,%s) "
            "ON CONFLICT(uid) DO UPDATE SET bound=true,template_reference=EXCLUDED.template_reference",
            (uid, reference),
        )


def _temporary_item_form(item):
    """Use the shared native vj binding codec for temporary and owned units."""
    from wakfu_server.inventory_items import item_form

    item = dict(item)
    if item.get("damage_elements") is None and item.get("resistance_elements") is None:
        item.pop("damage_elements", None)
        item.pop("resistance_elements", None)
    enum, binding_type, _ = _template_binding(item["reference"])
    if enum != "NOT_BOUND" or _effective_bound(item):
        item["binding_type"] = binding_type
        item["bound"] = _effective_bound(item)
    return item_form(item)


def temporary_section(db, character_id):
    """Encode signed-short length + lP ProtoTemporaryInventory for bootstrap."""
    from wakfu_server.wire import proto_field

    character_id = _integer(character_id, "temporary inventory owner", 1)
    rows = db.execute(
        "SELECT uid,character_id,reference,quantity,damage_elements,resistance_elements,bound "
        "FROM temporary_combat_items WHERE character_id=%s ORDER BY uid",
        (character_id,),
    ).fetchall()
    payload = b"".join(proto_field(10, _item_proto(dict(row))) for row in rows)
    if not payload:
        return b"\x00\x00"
    if len(payload) > 32767:
        raise ValueError(
            "Temporary inventory section exceeds native signed-short length"
        )
    return struct.pack(">h", len(payload)) + payload


def _equipped_uids(store, account_id, character_id, db):
    character = store.character(account_id, character_id, db)
    from wakfu_server.wire import proto_fields

    result = set()
    for build in character.get("builds", {}).values():
        for tag, value in proto_fields(bytes.fromhex(build.get("equipment", ""))):
            if tag == 10:
                fields = dict(proto_fields(value))
                uid = fields.get(8)
                if type(uid) is int:
                    result.add(uid)
    return result


def _element_selection(reference):
    from wakfu_server.inventory_elements import create

    return create(reference)


def _selection_key(item):
    from wakfu_server.inventory_elements import masks

    return masks(item)


def apply(store, db, batch):
    """Apply all accepted decisions once, placing any overflow durably.

    Existing stack merges require the exact native stack rule and identical
    element selections. Items that do not fit are retained in temporary storage
    with the same UID metadata; a full bag never drops an awarded quantity.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Combat drop delivery requires an active transaction")
    from wakfu_server.combat_drops import AwardBatch
    from wakfu_server.inventory_uids import allocate
    from wakfu_server.inventory_elements import hydrate, save

    if not isinstance(batch, AwardBatch):
        raise ValueError("Committed combat drop batch required")
    fight_id = _integer(batch.fight_id, "fight id", 1, 2**31 - 1)
    character_id = _integer(batch.character_id, "character id", 1)
    account_id = _integer(batch.snapshot.get("account_id"), "drop award account", 1)
    generation = batch.snapshot.get("generation")
    if not isinstance(generation, str) or not generation:
        raise ValueError("Drop award has no session generation")
    from wakfu_server.combat_reward_ownership import lock_recipient

    lock_recipient(store, db, account_id, generation, character_id, fight_id)
    award = db.execute(
        "SELECT account_id,generation,snapshot,snapshot_sha256 FROM fight_drop_awards "
        "WHERE fight_id=%s AND character_id=%s FOR UPDATE",
        (fight_id, character_id),
    ).fetchone()
    if (
        award is None
        or award["account_id"] != account_id
        or award["generation"] != generation
    ):
        raise ValueError("Drop delivery has no matching durable award")
    from hashlib import sha256
    from wakfu_server.combat_drops import _canonical_json

    if (
        sha256(_canonical_json(award["snapshot"]).encode("utf8")).hexdigest()
        != award["snapshot_sha256"]
    ):
        raise ValueError("Stored drop award snapshot hash is invalid")
    if (
        award["snapshot"] != batch.snapshot
        or award["snapshot_sha256"] != batch.snapshot_sha256
    ):
        raise ValueError("Drop batch differs from durable award snapshot")
    accepted = [entry for entry in batch.decisions if entry.success]
    if not accepted:
        return []

    attempts = []
    for entry in accepted:
        row = db.execute(
            "SELECT item_reference,quantity FROM fight_drop_attempt_receipts "
            "WHERE fight_id=%s AND character_id=%s AND defeated_actor_id=%s "
            "AND drop_row_index=%s AND attempt_index=%s AND success=true FOR UPDATE",
            (
                fight_id,
                character_id,
                entry.defeated_actor_id,
                entry.drop_row_index,
                entry.attempt_index,
            ),
        ).fetchone()
        if (
            row is None
            or row["item_reference"] != entry.item_reference
            or row["quantity"] != entry.quantity
        ):
            raise ValueError("Drop decision has no matching durable success receipt")
        existing = db.execute(
            "SELECT * FROM fight_drop_delivery_receipts WHERE fight_id=%s AND character_id=%s "
            "AND defeated_actor_id=%s AND drop_row_index=%s AND attempt_index=%s FOR UPDATE",
            (
                fight_id,
                character_id,
                entry.defeated_actor_id,
                entry.drop_row_index,
                entry.attempt_index,
            ),
        ).fetchone()
        if existing is not None:
            temporary = db.execute(
                "SELECT uid FROM temporary_combat_items WHERE fight_id=%s AND character_id=%s "
                "AND defeated_actor_id=%s AND drop_row_index=%s AND attempt_index=%s",
                (
                    fight_id,
                    character_id,
                    entry.defeated_actor_id,
                    entry.drop_row_index,
                    entry.attempt_index,
                ),
            ).fetchone()
            saved = dict(existing)
            saved["reference"] = saved.pop("item_reference")
            saved.pop("created_at", None)
            saved["temporary_uid"] = None if temporary is None else temporary["uid"]
            attempts.append((entry, saved, None))
            continue
        rule = STACKS.get(entry.item_reference)
        if (
            rule is None
            or type(entry.quantity) is not int
            or not 1 <= entry.quantity <= 32767
        ):
            raise ValueError("Drop item lacks a supported native inventory rule")
        # Fail closed if the item template is missing or has unverified binding
        # semantics. In particular, native BOUND_ON_PICKUP drops must retain it.
        _template_bound(entry.item_reference)
        if (
            db.execute(
                "SELECT 1 FROM mount_models WHERE reference=%s", (entry.item_reference,)
            ).fetchone()
            is not None
        ):
            raise ValueError("Combat drop unexpectedly resolves to a mount model")
        attempts.append((entry, None, _element_selection(entry.item_reference)))

    if all(existing is not None for _, existing, _ in attempts):
        return [dict(existing) for _, existing, _ in attempts]

    containers = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid FOR UPDATE",
            (character_id,),
        ).fetchall()
    ]
    items = hydrate(
        db,
        [
            dict(row)
            for row in db.execute(
                "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid FOR UPDATE",
                (character_id,),
            ).fetchall()
        ],
    )
    identified = _identified_uids(db, items)
    item_bindings = _binding_rows(db, items)
    for item in items:
        item["bound"] = item_bindings.get(item["uid"], False)
    equipped = _equipped_uids(store, batch.snapshot.get("account_id"), character_id, db)
    slot_use = {container["uid"]: set() for container in containers}
    for item in items:
        if (
            item["container"] not in slot_use
            or item["slot"] in slot_use[item["container"]]
        ):
            raise ValueError("Invalid owned inventory slots during drop delivery")
        slot_use[item["container"]].add(item["slot"])
    by_uid = {item["uid"]: item for item in items}
    results = []

    for entry, existing, selection in attempts:
        if existing is not None:
            results.append(dict(existing))
            continue
        rule = STACKS[entry.item_reference]
        drop_bound = _template_bound(entry.item_reference)
        remaining = entry.quantity
        selected_masks = None if selection is None else _selection_key(selection)
        inventory_quantity = 0
        from wakfu_server.items import quest_inventory

        if entry.item_reference in quest_inventory.REFERENCES:
            quest_inventory.grant(db, character_id, entry.item_reference, remaining)
            inventory_quantity = remaining
            remaining = 0
        for target in sorted(by_uid.values(), key=lambda row: row["uid"]):
            if (
                remaining == 0
                or not rule["minimal_mergeable"]
                or target["uid"] in equipped
                or target["uid"] in identified
                or target["reference"] != entry.item_reference
                or _effective_bound(target) != drop_bound
                or _selection_key(target) != selected_masks
            ):
                continue
            moved = min(remaining, rule["maximum"] - target["quantity"])
            if moved <= 0:
                continue
            target["quantity"] += moved
            db.execute(
                "UPDATE inventory_items SET quantity=%s WHERE uid=%s",
                (target["quantity"], target["uid"]),
            )
            remaining -= moved
            inventory_quantity += moved
            if remaining == 0:
                break

        new_rows = []
        if remaining:
            for container in containers:
                if not _container_can_hold(container, character_id):
                    continue
                for slot in range(container["capacity"]):
                    if slot in slot_use[container["uid"]]:
                        continue
                    amount = min(remaining, rule["maximum"])
                    uid = allocate(db)
                    new_item = dict(
                        uid=uid,
                        character_id=character_id,
                        reference=entry.item_reference,
                        quantity=amount,
                        container=container["uid"],
                        slot=slot,
                        bound=drop_bound,
                    )
                    if selection is not None:
                        new_item.update(selection)
                    new_rows.append(new_item)
                    by_uid[uid] = new_item
                    slot_use[container["uid"]].add(slot)
                    remaining -= amount
                    inventory_quantity += amount
                    if remaining == 0:
                        break
                if remaining == 0:
                    break

        temporary_uid = None
        if remaining:
            temporary_uid = allocate(db)
        temporary_quantity = remaining
        db.execute(
            "INSERT INTO fight_drop_delivery_receipts "
            "(fight_id,character_id,defeated_actor_id,drop_row_index,attempt_index,item_reference,"
            "awarded_quantity,inventory_quantity,temporary_quantity) "
            "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (
                fight_id,
                character_id,
                entry.defeated_actor_id,
                entry.drop_row_index,
                entry.attempt_index,
                entry.item_reference,
                entry.quantity,
                inventory_quantity,
                temporary_quantity,
            ),
        )
        for item in new_rows:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    item["uid"],
                    item["character_id"],
                    item["reference"],
                    item["quantity"],
                    item["container"],
                    item["slot"],
                ),
            )
            if selection is not None:
                save(db, item["uid"], selection)
            _save_binding(db, item["uid"], item["reference"], item["bound"])
        if temporary_uid is not None:
            db.execute(
                "INSERT INTO temporary_combat_items "
                "(uid,character_id,reference,quantity,damage_elements,resistance_elements,bound,"
                "fight_id,defeated_actor_id,drop_row_index,attempt_index) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    temporary_uid,
                    character_id,
                    entry.item_reference,
                    temporary_quantity,
                    None if selected_masks is None else selected_masks[0],
                    None if selected_masks is None else selected_masks[1],
                    drop_bound,
                    fight_id,
                    entry.defeated_actor_id,
                    entry.drop_row_index,
                    entry.attempt_index,
                ),
            )
        results.append(
            dict(
                fight_id=fight_id,
                character_id=character_id,
                defeated_actor_id=entry.defeated_actor_id,
                drop_row_index=entry.drop_row_index,
                attempt_index=entry.attempt_index,
                reference=entry.item_reference,
                awarded_quantity=entry.quantity,
                inventory_quantity=inventory_quantity,
                temporary_quantity=temporary_quantity,
                temporary_uid=temporary_uid,
            )
        )
    return results


def temporary_update(db, character_id):
    """12691/CLEAR + complete ADD_ITEM snapshot for a live lease refresh."""
    rows = db.execute(
        "SELECT uid,character_id,reference,quantity,damage_elements,resistance_elements,bound "
        "FROM temporary_combat_items WHERE character_id=%s ORDER BY uid",
        (character_id,),
    ).fetchall()
    body = bytearray(struct.pack(">q", _integer(character_id, "temporary owner", 1)))
    body.append(3)  # Native CLEAR event has an empty payload.
    for row in rows:
        body.append(0)  # Native ADD_ITEM event contains a vj binary item.
        item = dict(row)
        if item["damage_elements"] is None and item["resistance_elements"] is None:
            item.pop("damage_elements")
            item.pop("resistance_elements")
        body.extend(_temporary_item_form(item))
    return (12691, bytes(body))


def discard(store, account_id, generation, character_id, body):
    """Discard the currently visible temporary loot after native close 12561.

    The native request has an empty body, so it has no operation token. We bind
    the durable receipt to the exact locked row snapshot instead: reconnecting
    with the same empty state is idempotent, while a later close after new drops
    has a different identity. The server cannot distinguish a delayed duplicate
    from a new close if new rows arrived in between; TCP ordering is the only
    available boundary in this protocol.
    """
    if not isinstance(body, (bytes, bytearray)) or len(body) != 0:
        raise ValueError("Invalid12561 request body")
    from wakfu_server.inventory_items import _lease

    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        rows = db.execute(
            "SELECT uid,reference,quantity,damage_elements,resistance_elements,bound "
            "FROM temporary_combat_items WHERE character_id=%s ORDER BY uid FOR UPDATE",
            (character_id,),
        ).fetchall()
        snapshot = {
            "character_id": character_id,
            "items": [
                [
                    row["uid"],
                    row["reference"],
                    row["quantity"],
                    row["damage_elements"],
                    row["resistance_elements"],
                    row["bound"],
                ]
                for row in rows
            ],
        }
        import json

        # Use a non-empty synthetic body because migration 043 deliberately
        # rejects empty receipt bodies. It is not the native request payload.
        receipt_body = b"12561-discard\0" + json.dumps(
            snapshot, separators=(",", ":"), ensure_ascii=True
        ).encode("ascii")
        already_discarded = _prior_transfer(
            db, character_id, 3, receipt_body, character_id
        )
        if not already_discarded and rows:
            db.execute(
                "DELETE FROM temporary_combat_items WHERE character_id=%s AND uid=ANY(%s)",
                (character_id, [row["uid"] for row in rows]),
            )
            _record_transfer(db, character_id, 3, receipt_body, character_id)
        elif not already_discarded:
            # Record the empty snapshot too; repeated closes in the same state
            # have a durable, harmless outcome.
            _record_transfer(db, character_id, 3, receipt_body, character_id)
        return {
            "applied": bool(rows) and not already_discarded,
            "packets": [temporary_update(db, character_id)],
        }


def _prior_transfer(db, source_character_id, operation, body, destination_character_id):
    digest = sha256(bytes(body)).hexdigest()
    row = db.execute(
        "SELECT request_body,destination_character_id FROM temporary_inventory_transfer_receipts "
        "WHERE source_character_id=%s AND operation=%s AND request_sha256=%s FOR UPDATE",
        (source_character_id, operation, digest),
    ).fetchone()
    if row is None:
        return False
    if (
        bytes(row["request_body"]) != bytes(body)
        or row["destination_character_id"] != destination_character_id
    ):
        raise ValueError("Temporary inventory request identity collision")
    return True


def _record_transfer(
    db, source_character_id, operation, body, destination_character_id
):
    db.execute(
        "INSERT INTO temporary_inventory_transfer_receipts "
        "(source_character_id,operation,request_sha256,request_body,destination_character_id) "
        "VALUES(%s,%s,%s,%s,%s)",
        (
            source_character_id,
            operation,
            sha256(bytes(body)).hexdigest(),
            bytes(body),
            destination_character_id,
        ),
    )


def _bulk_self_transfer(store, account_id, db, character_id, rows):
    """Move a native Get All UID selection into this same character's bags.

    The client sends the current actor as both cpX source and destination.
    Compatible stacks are merged before free slots are required, so a full bag
    can still receive loot that fits an existing native stack.
    """
    from wakfu_server.inventory_elements import hydrate, masks, save
    from wakfu_server.inventory_uids import allocate

    containers = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid FOR UPDATE",
            (character_id,),
        ).fetchall()
    ]
    containers = [
        item for item in containers if _container_can_hold(item, character_id)
    ]
    if not containers:
        raise ValueError("12294 destination has no ordinary inventory bag")
    container_by_uid = {item["uid"]: item for item in containers}
    contents = hydrate(
        db,
        [
            dict(row)
            for row in db.execute(
                "SELECT * FROM inventory_items WHERE character_id=%s AND container=ANY(%s) "
                "ORDER BY container,slot FOR UPDATE",
                (character_id, list(container_by_uid)),
            ).fetchall()
        ],
    )
    excluded = _identified_uids(db, contents)
    excluded.update(_equipped_uids(store, account_id, character_id, db))
    bindings = _binding_rows(db, contents)
    by_container = {uid: {} for uid in container_by_uid}
    for item in contents:
        if item["container"] not in by_container:
            raise ValueError("12294 source inventory has a foreign container")
        item["bound"] = bindings.get(item["uid"], False)
        by_container[item["container"]][item["slot"]] = item

    plan_updates = {}
    plan_new = []
    new_uids = set()
    normalized_rows = []
    for row in rows:
        item = dict(row)
        item["bound"] = _effective_bound(item)
        if item["damage_elements"] is None and item["resistance_elements"] is None:
            item.pop("damage_elements")
            item.pop("resistance_elements")
        selected_masks = masks(item)
        rule = STACKS.get(item["reference"])
        if rule is None:
            raise ValueError("12294 item has no native stack rule")
        normalized_rows.append((item, selected_masks, rule))

    for selected, selected_masks, rule in normalized_rows:
        remaining = selected["quantity"]
        if rule["minimal_mergeable"]:
            for container in containers:
                for slot in sorted(by_container[container["uid"]]):
                    target = by_container[container["uid"]][slot]
                    if (
                        target["uid"] in excluded
                        or target["reference"] != selected["reference"]
                        or _effective_bound(target) != selected["bound"]
                        or masks(target) != selected_masks
                    ):
                        continue
                    amount = min(
                        remaining, max(0, rule["maximum"] - target["quantity"])
                    )
                    if amount <= 0:
                        continue
                    target["quantity"] += amount
                    if target["uid"] in new_uids:
                        pass  # Already included in plan_new by reference.
                    else:
                        plan_updates[target["uid"]] = target["quantity"]
                    remaining -= amount
                    if remaining == 0:
                        break
                if remaining == 0:
                    break
        for container in containers:
            occupied = by_container[container["uid"]]
            for slot in range(container["capacity"]):
                if slot in occupied:
                    continue
                if remaining <= 0:
                    break
                amount = min(remaining, rule["maximum"])
                target = dict(
                    uid=allocate(db),
                    character_id=character_id,
                    reference=selected["reference"],
                    quantity=amount,
                    container=container["uid"],
                    slot=slot,
                    bound=selected["bound"],
                )
                if selected_masks is not None:
                    target.update(
                        damage_elements=selected["damage_elements"],
                        resistance_elements=selected["resistance_elements"],
                    )
                plan_new.append(target)
                new_uids.add(target["uid"])
                occupied[slot] = target
                remaining -= amount
            if remaining <= 0:
                break
        if remaining:
            raise ValueError("12294 destination inventory is full")

    for uid, quantity in plan_updates.items():
        db.execute(
            "UPDATE inventory_items SET quantity=%s WHERE uid=%s", (quantity, uid)
        )
    for item in rows:
        db.execute("DELETE FROM temporary_combat_items WHERE uid=%s", (item["uid"],))
    for item in plan_new:
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (
                item["uid"],
                item["character_id"],
                item["reference"],
                item["quantity"],
                item["container"],
                item["slot"],
            ),
        )
        if "damage_elements" in item or "resistance_elements" in item:
            save(db, item["uid"], item)
        _save_binding(db, item["uid"], item["reference"], item["bound"])


def _inventory_snapshot(store, account_id, character_id, db):
    character = store.character(account_id, character_id, db)
    from wakfu_server.inventory_move import synchronization
    from wakfu_server.inventory_items import equipment_inventory

    return character, [synchronization(character), equipment_inventory(character)]


def decode_claim(body):
    if not isinstance(body, (bytes, bytearray)) or len(body) != 21:
        raise ValueError("Invalid13993 request length")
    uid, quantity, destination_type, destination_uid, position = struct.unpack(
        ">qh b q h", body
    )
    if (
        uid <= 0
        or quantity <= 0
        or destination_uid <= 0
        or destination_type != -1
        or position < -1
    ):
        raise ValueError("Invalid13993 request fields")
    return dict(
        uid=uid,
        quantity=quantity,
        destination_type=destination_type,
        destination_uid=destination_uid,
        position=position,
    )


def claim(store, account_id, generation, character_id, body):
    """Move a temporary unit quantity into an owned bag atomically.

    The client sends destination UID and position. The method returns complete
    inventory and temporary snapshots so callers can publish only after commit.
    """
    from wakfu_server.inventory_items import _lease
    from wakfu_server.inventory_uids import allocate
    from wakfu_server.inventory_elements import masks, save

    request = decode_claim(body)
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        if _prior_transfer(db, character_id, 1, body, character_id):
            character, packets = _inventory_snapshot(
                store, account_id, character_id, db
            )
            return dict(
                character=character,
                packets=packets + [temporary_update(db, character_id)],
                applied=False,
            )
        source = db.execute(
            "SELECT * FROM temporary_combat_items WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["uid"], character_id),
        ).fetchone()
        container = db.execute(
            "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s FOR UPDATE",
            (request["destination_uid"], character_id),
        ).fetchone()
        if source is None or container is None:
            raise ValueError("Temporary item or destination is unavailable")
        if not _container_can_hold(dict(container), character_id):
            raise ValueError(
                "Specialized inventory bag cannot receive a temporary item"
            )
        rule = STACKS.get(source["reference"])
        if (
            rule is None
            or request["quantity"] > rule["maximum"] * container["capacity"]
        ):
            raise ValueError("Requested amount exceeds native destination capacity")

        def normalized(row):
            item = dict(row)
            item["bound"] = _effective_bound(item)
            if item["damage_elements"] is None and item["resistance_elements"] is None:
                item.pop("damage_elements")
                item.pop("resistance_elements")
            return item, masks(item)

        selected, selected_masks = normalized(source)
        # The native temporary window groups equivalent rows visually and can
        # send the displayed total with one representative UID. Lock and
        # consume only stacks with the same reference, binding and elements.
        grouped = []
        for row in db.execute(
            "SELECT * FROM temporary_combat_items WHERE character_id=%s AND reference=%s "
            "ORDER BY uid FOR UPDATE",
            (character_id, source["reference"]),
        ).fetchall():
            item, item_masks = normalized(row)
            if item["bound"] == selected["bound"] and item_masks == selected_masks:
                grouped.append(dict(row))
        grouped.sort(key=lambda row: (row["uid"] != source["uid"], row["uid"]))
        if request["quantity"] > sum(row["quantity"] for row in grouped):
            raise ValueError("Requested amount exceeds compatible temporary quantity")

        position = request["position"]
        slots = db.execute(
            "SELECT * FROM inventory_items WHERE container=%s ORDER BY slot FOR UPDATE",
            (container["uid"],),
        ).fetchall()
        from wakfu_server.inventory_elements import hydrate

        hydrated = hydrate(db, [dict(row) for row in slots])
        excluded = _identified_uids(db, hydrated)
        excluded.update(_equipped_uids(store, account_id, character_id, db))
        bindings = _binding_rows(db, hydrated)
        by_slot = {row["slot"]: dict(row) for row in hydrated}
        if position < -1 or position >= container["capacity"]:
            raise ValueError("Destination container is full")

        plan_updates = []
        plan_new = []
        remaining = request["quantity"]
        if position >= 0 and position in by_slot:
            merge_slots = [position]
        elif position == -1:
            merge_slots = sorted(by_slot)
        else:
            merge_slots = []
        for slot in merge_slots:
            target = by_slot[slot]
            target["bound"] = bindings.get(target["uid"], False)
            compatible = (
                rule["minimal_mergeable"]
                and target["uid"] not in excluded
                and target["reference"] == source["reference"]
                and _effective_bound(target) == selected["bound"]
                and masks(target) == selected_masks
            )
            if not compatible:
                if position == slot:
                    raise ValueError(
                        "Destination slot cannot receive this temporary item"
                    )
                continue
            moved = min(remaining, max(0, rule["maximum"] - target["quantity"]))
            if moved:
                target["quantity"] += moved
                plan_updates.append(target)
                remaining -= moved
            if remaining == 0:
                break

        free_slots = [
            slot for slot in range(container["capacity"]) if slot not in by_slot
        ]
        if position >= 0 and position in free_slots:
            free_slots.remove(position)
            free_slots.insert(0, position)
        for slot in free_slots:
            if remaining <= 0:
                break
            amount = min(rule["maximum"], remaining)
            uid = allocate(db)
            item = dict(
                uid=uid,
                character_id=character_id,
                reference=source["reference"],
                quantity=amount,
                container=container["uid"],
                slot=slot,
                damage_elements=selected.get("damage_elements"),
                resistance_elements=selected.get("resistance_elements"),
                bound=selected["bound"],
            )
            plan_new.append(item)
            remaining -= amount
        if remaining:
            raise ValueError("Destination container has insufficient capacity")
        for target in plan_updates:
            db.execute(
                "UPDATE inventory_items SET quantity=%s WHERE uid=%s",
                (target["quantity"], target["uid"]),
            )
        consume = request["quantity"]
        for row in grouped:
            if consume <= 0:
                break
            moved = min(consume, row["quantity"])
            left = row["quantity"] - moved
            if left:
                db.execute(
                    "UPDATE temporary_combat_items SET quantity=%s WHERE uid=%s",
                    (left, row["uid"]),
                )
            else:
                db.execute(
                    "DELETE FROM temporary_combat_items WHERE uid=%s", (row["uid"],)
                )
            consume -= moved
        for item in plan_new:
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    item["uid"],
                    item["character_id"],
                    item["reference"],
                    item["quantity"],
                    item["container"],
                    item["slot"],
                ),
            )
            if selected_masks is not None:
                save(db, item["uid"], selected)
            _save_binding(db, item["uid"], item["reference"], item["bound"])
        _record_transfer(db, character_id, 1, body, character_id)
        character, packets = _inventory_snapshot(store, account_id, character_id, db)
        return dict(
            character=character,
            packets=packets + [temporary_update(db, character_id)],
            applied=True,
        )


def decode_bulk_transfer(body):
    if not isinstance(body, (bytes, bytearray)) or len(body) < 18:
        raise ValueError("Invalid12294 request length")
    source, destination, count = struct.unpack_from(">qqh", body)
    if source <= 0 or destination <= 0 or count <= 0 or len(body) != 18 + count * 8:
        raise ValueError("Invalid12294 request fields")
    uids = list(struct.unpack_from(f">{count}q", body, 18))
    if any(uid <= 0 for uid in uids) or len(set(uids)) != len(uids):
        raise ValueError("Invalid12294 item identities")
    return dict(source_character=source, destination_character=destination, uids=uids)


def bulk_transfer(store, account_id, generation, character_id, body):
    """Move the requested temporary UIDs between two characters of one account."""
    from wakfu_server.inventory_items import _lease

    request = decode_bulk_transfer(body)
    if request["source_character"] != character_id:
        raise ValueError("12294 source must be the selected character")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character_id)
        owner = db.execute(
            "SELECT id FROM characters WHERE id=%s AND account_id=%s FOR UPDATE",
            (request["destination_character"], account_id),
        ).fetchone()
        if owner is None:
            raise ValueError("12294 destination must belong to the same account")
        if _prior_transfer(db, character_id, 2, body, request["destination_character"]):
            source_character, source_packets = _inventory_snapshot(
                store, account_id, character_id, db
            )
            destination_character, destination_packets = _inventory_snapshot(
                store, account_id, request["destination_character"], db
            )
            return dict(
                source=source_character,
                destination=destination_character,
                packets=source_packets
                + [temporary_update(db, character_id)]
                + destination_packets,
                applied=False,
            )
        rows = db.execute(
            "SELECT * FROM temporary_combat_items WHERE character_id=%s AND uid=ANY(%s) ORDER BY uid FOR UPDATE",
            (character_id, request["uids"]),
        ).fetchall()
        if len(rows) != len(request["uids"]):
            raise ValueError("12294 includes a foreign or unavailable temporary UID")
        if request["destination_character"] == character_id:
            _bulk_self_transfer(store, account_id, db, character_id, rows)
            _record_transfer(db, character_id, 2, body, character_id)
            character, packets = _inventory_snapshot(
                store, account_id, character_id, db
            )
            return dict(
                source=character,
                destination=character,
                packets=packets + [temporary_update(db, character_id)],
                applied=True,
            )
        containers = [
            dict(row)
            for row in db.execute(
                "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid FOR UPDATE",
                (request["destination_character"],),
            ).fetchall()
        ]
        containers = [
            container
            for container in containers
            if _container_can_hold(container, request["destination_character"])
        ]
        occupied = {
            row["uid"]: {
                r["slot"]
                for r in db.execute(
                    "SELECT slot FROM inventory_items WHERE container=%s FOR UPDATE",
                    (row["uid"],),
                )
            }
            for row in containers
        }
        plan = []
        for row in rows:
            destination = None
            for container in containers:
                if container["kind"] not in (0, 1, 2, 3):
                    continue
                slot = next(
                    (
                        n
                        for n in range(container["capacity"])
                        if n not in occupied[container["uid"]]
                    ),
                    None,
                )
                if slot is not None:
                    destination = (container, slot)
                    break
            if destination is None:
                raise ValueError("12294 destination inventory is full")
            container, slot = destination
            occupied[container["uid"]].add(slot)
            plan.append((dict(row), container, slot))
        from wakfu_server.inventory_elements import save

        for row, container, slot in plan:
            bound = _effective_bound(dict(row))
            db.execute("DELETE FROM temporary_combat_items WHERE uid=%s", (row["uid"],))
            db.execute(
                "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
                "VALUES(%s,%s,%s,%s,%s,%s)",
                (
                    row["uid"],
                    request["destination_character"],
                    row["reference"],
                    row["quantity"],
                    container["uid"],
                    slot,
                ),
            )
            if row["damage_elements"] is not None:
                save(db, row["uid"], row)
            _save_binding(db, row["uid"], row["reference"], bound)
        _record_transfer(db, character_id, 2, body, request["destination_character"])
        source_character, source_packets = _inventory_snapshot(
            store, account_id, character_id, db
        )
        destination_character, destination_packets = _inventory_snapshot(
            store, account_id, request["destination_character"], db
        )
        return dict(
            source=source_character,
            destination=destination_character,
            packets=source_packets
            + [temporary_update(db, character_id)]
            + destination_packets,
            applied=True,
        )
