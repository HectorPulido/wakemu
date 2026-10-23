"""Native Ranch reward ledger selection and atomic ordinary item delivery."""
import struct


def decode_all(body):
    if not isinstance(body, bytes) or not body or body[0] not in (0, 1):
        raise ValueError("Invalid native Ranch reward filter")
    expected = 17 if body[0] else 9
    if len(body) != expected:
        raise ValueError("Invalid native12068 reward request length")
    values = struct.unpack(">qq" if body[0] else ">q", body[1:])
    monster, recipient = values if body[0] else (None, values[0])
    if recipient <= 0 or monster is not None and monster <= 0:
        raise ValueError("Invalid native Ranch reward recipient/filter")
    return monster, recipient


def decode_selected(body):
    if not isinstance(body, bytes) or len(body) < 12:
        raise ValueError("Invalid native12320 reward request")
    count = struct.unpack_from(">h", body)[0]
    if count <= 0 or len(body) != 12 + 8 * count:
        raise ValueError("Invalid native Ranch reward selection count")
    uids = struct.unpack_from(">" + "q" * count, body, 2)
    bag, slot = struct.unpack_from(">qh", body, 2 + 8 * count)
    if any(uid <= 0 for uid in uids) or len(set(uids)) != count or bag <= 0 or slot < 0:
        raise ValueError("Invalid native Ranch reward destination/identities")
    return uids, bag, slot


def _record(row):
    return dict(
        uid=row["uid"],
        reference=row["item_ref"],
        quantity=row["quantity"],
        monster_uid=row["monster_uid"],
        drop_date_ms=row["drop_date_ms"],
        retrieved=row["retrieved_at"] is not None,
    )


def encode_reward(row):
    values = (
        row["uid"],
        row["reference"],
        row["quantity"],
        row["monster_uid"],
        row["drop_date_ms"],
    )
    if (
        any(type(v) is not int for v in values)
        or values[0] <= 0
        or values[1] <= 0
        or not 1 <= values[2] <= 32767
        or values[3] <= 0
        or values[4] < 0
        or type(row["retrieved"]) is not bool
    ):
        raise ValueError("Invalid complete native fBU reward")
    return struct.pack(">qihqqB", *values, row["retrieved"])


def changed(scene_id, rows):
    if type(scene_id) is not int or scene_id <= 0 or len(rows) > 32767:
        raise ValueError("Invalid Ranch reward publication")
    return (
        13964,
        struct.pack(">qh", scene_id, len(rows)) + b"".join(map(encode_reward, rows)),
    )


def records(db, account_id, *, pending_only=False):
    suffix = " AND retrieved_at IS NULL" if pending_only else ""
    return [
        _record(row)
        for row in db.execute(
            "SELECT * FROM account_ranch_rewards WHERE account_id=%s"
            + suffix
            + " ORDER BY uid",
            (account_id,),
        )
    ]


def insert_pending(
    db,
    *,
    account_id,
    monster_uid,
    cycle_number,
    drop_date_ms,
    items,
    earned_carry=False
):
    """Caller owns the creature/account lock; repeat insertion must match exactly."""
    from wakfu_server.inventory_uids import allocate

    if (
        any(
            type(value) is not int
            for value in (account_id, monster_uid, cycle_number, drop_date_ms)
        )
        or account_id <= 0
        or monster_uid <= 0
        or cycle_number < 0
        or drop_date_ms < 0
        or not isinstance(items, list)
        or type(earned_carry) is not bool
    ):
        raise ValueError("Invalid produced Ranch reward cycle")
    if earned_carry:
        if (
            db.execute(
                "SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account_id,)
            ).fetchone()
            is None
        ):
            raise ValueError("Missing earned Ranch reward account")
    creature = db.execute(
        "SELECT * FROM account_ranch_creatures WHERE uid=%s AND account_id=%s FOR UPDATE",
        (monster_uid, account_id),
    ).fetchone()
    if creature is None:
        raise ValueError("Foreign Ranch reward creature")
    released = creature["released_at"] is not None
    if released != earned_carry:
        raise ValueError("Released Ranch creatures require a proven earned-cycle carry")
    if earned_carry:
        from wakfu_server.ranch_cycle_rewards import catalog, consume_intervals

        clock = db.execute(
            "SELECT * FROM account_ranch_cycle_progress WHERE monster_uid=%s FOR UPDATE",
            (monster_uid,),
        ).fetchone()
        definition = catalog()[0].get(creature["definition"])
        if clock is None or definition is None:
            raise ValueError("Missing durable earned Ranch cycle authority")
        cycle_ms = definition["cycle_seconds"] * 1000
        dates, _ = consume_intervals(clock["earned_intervals"], cycle_ms)
        index = cycle_number - clock["cycle_number"]
        # The producer calls before consuming the original queued intervals.
        # Its shared helper validates ordering and the settlement budget. A
        # paused/released gap never contributes duration or moves a drop date.
        if (
            sum(end - start for start, end in clock["earned_intervals"])
            != creature["native_tjr"]
            or any(
                end > clock["last_observed_ms"]
                for start, end in clock["earned_intervals"]
            )
            or not 1 <= index <= len(dates)
            or drop_date_ms != dates[index - 1]
        ):
            raise ValueError(
                "Released Ranch reward is outside its frozen earned-cycle budget"
            )
    for item in items:
        if (
            not isinstance(item, dict)
            or set(item) != {"reference", "quantity"}
            or type(item["reference"]) is not int
            or item["reference"] <= 0
            or type(item["quantity"]) is not int
            or not 1 <= item["quantity"] <= 32767
        ):
            raise ValueError("Invalid produced Ranch reward item")
    from psycopg.types.json import Jsonb

    batch = db.execute(
        "SELECT * FROM account_ranch_reward_batches WHERE monster_uid=%s "
        "AND cycle_number=%s FOR UPDATE",
        (monster_uid, cycle_number),
    ).fetchone()
    if batch is not None and (
        batch["account_id"] != account_id
        or batch["items"] != items
        or batch["drop_date_ms"] != drop_date_ms
    ):
        raise ValueError("Produced Ranch cycle differs from its frozen reward batch")
    old = list(
        db.execute(
            "SELECT * FROM account_ranch_rewards WHERE monster_uid=%s "
            "AND cycle_number=%s ORDER BY entry_index FOR UPDATE",
            (monster_uid, cycle_number),
        )
    )
    if batch is not None:
        if len(old) != len(items) or any(
            row["account_id"] != account_id
            or row["entry_index"] != index
            or row["item_ref"] != items[index]["reference"]
            or row["quantity"] != items[index]["quantity"]
            or row["drop_date_ms"] != drop_date_ms
            for index, row in enumerate(old)
        ):
            raise ValueError(
                "Produced Ranch cycle conflicts with durable reward identities"
            )
        return [_record(row) for row in old]
    if old:
        raise ValueError("Ranch reward rows are missing their frozen batch")
    db.execute(
        "INSERT INTO account_ranch_reward_batches(monster_uid,cycle_number,account_id,drop_date_ms,items) "
        "VALUES(%s,%s,%s,%s,%s)",
        (monster_uid, cycle_number, account_id, drop_date_ms, Jsonb(items)),
    )
    result = []
    for index, item in enumerate(items):
        row = db.execute(
            "INSERT INTO account_ranch_rewards(uid,account_id,monster_uid,cycle_number,"
            "entry_index,item_ref,quantity,drop_date_ms) VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
            (
                allocate(db),
                account_id,
                monster_uid,
                cycle_number,
                index,
                item["reference"],
                item["quantity"],
                drop_date_ms,
            ),
        ).fetchone()
        result.append(_record(row))
    return result


def _target_grant(store, db, account, generation, character, rows, bag_uid, slot):
    """Native drag transfers whole same-reference reward rows into one slot."""
    from wakfu_server import inventory_items
    from wakfu_server.inventory_move import ACQUISITION_STACKS
    from wakfu_server.combat_drop_delivery import (
        _container_can_hold,
        _template_bound,
        _effective_bound,
        _binding_rows,
    )
    from wakfu_server.item_custody_metadata import snapshot_many
    from wakfu_server.item_set_assembly import validate_input_metadata
    from wakfu_server.simple_item_actions import _equipped
    from wakfu_server import quest_inventory, account_quest_inventory

    references = {row["item_ref"] for row in rows}
    if len(references) != 1:
        raise ValueError("A native reward drag requires a same-item group")
    (reference,) = references
    quantity = sum(row["quantity"] for row in rows)
    rule = ACQUISITION_STACKS.get(reference)
    if (
        rule is None
        or reference in quest_inventory.REFERENCES | account_quest_inventory.REFERENCES
        or quantity > rule["maximum"]
        or quantity > 32767
    ):
        raise ValueError("Reward group does not fit one native destination stack")
    bag = db.execute(
        "SELECT * FROM inventory_containers WHERE uid=%s AND character_id=%s FOR UPDATE",
        (bag_uid, character["id"]),
    ).fetchone()
    if (
        bag is None
        or not _container_can_hold(bag, character["id"])
        or slot >= bag["capacity"]
    ):
        raise ValueError("Invalid owned ordinary reward destination")
    existing = db.execute(
        "SELECT * FROM inventory_items WHERE container=%s AND slot=%s FOR UPDATE",
        (bag_uid, slot),
    ).fetchone()
    if existing is None:
        item = inventory_items.grant(
            store,
            account,
            generation,
            character["id"],
            reference=reference,
            quantity=quantity,
            container=bag_uid,
            slot=slot,
            allowed_references=ACQUISITION_STACKS,
            db=db,
        )
        return [inventory_items.insertion(item, notification=True)]
    if (
        existing["reference"] != reference
        or not rule.get("minimal_mergeable")
        or existing["quantity"] + quantity > rule["maximum"]
    ):
        raise ValueError(
            "Reward destination is occupied or cannot merge the complete selection"
        )
    metadata = snapshot_many(db, [existing["uid"]])[existing["uid"]]
    if (
        _equipped(character, existing["uid"])
        or "inventory_item_recycling_state" in metadata
    ):
        raise ValueError(
            "An equipped or identified item cannot receive a new reward stack"
        )
    validate_input_metadata(metadata)
    bindings = _binding_rows(db, [existing])
    if _effective_bound(
        dict(existing, bound=bindings.get(existing["uid"], False))
    ) != _template_bound(reference):
        raise ValueError(
            "Reward destination binding differs from its native item template"
        )
    db.execute(
        "UPDATE inventory_items SET quantity=quantity+%s WHERE uid=%s",
        (quantity, existing["uid"]),
    )
    return [(12470, struct.pack(">qh", existing["uid"], quantity))]


def retrieve(store, account_id, generation, character, opcode, body, *, session):
    """Use actual owner/loaded recipient and atomically deliver selected fBU rows."""
    from wakfu_server.haven_ranch_herd import _authorize_scene
    from wakfu_server.inventory_owner import lock_inventory_character
    from wakfu_server.simple_item_actions import _idle
    from wakfu_server.item_action_delivery import grant_outputs

    if opcode == 12068:
        monster, recipient = decode_all(body)
        selection, bag, slot = None, None, None
    elif opcode == 12320:
        selection, bag, slot = decode_selected(body)
        monster, recipient = None, None
    else:
        raise ValueError("Unknown native Ranch reward retrieval opcode")
    with store.connection() as db:
        _authorize_scene(store, db, account_id, generation, character, session)
        if recipient is None:
            target = db.execute(
                "SELECT character_id FROM inventory_containers WHERE uid=%s", (bag,)
            ).fetchone()
            if target is None:
                raise ValueError("Unknown reward recipient bag")
            recipient = target["character_id"]
        lock_inventory_character(store, db, account_id, generation, recipient)
        _idle(db, recipient, store.now())
        from wakfu_server.ranch_cycle_rewards import settle_account

        settle_account(
            db, store, account_id, now_ms=int(store.now().timestamp() * 1000)
        )
        if (
            monster is not None
            and db.execute(
                "SELECT 1 FROM account_ranch_creatures WHERE uid=%s AND account_id=%s",
                (monster, account_id),
            ).fetchone()
            is None
        ):
            raise ValueError("Foreign Ranch reward filter")
        sql, args = "SELECT * FROM account_ranch_rewards WHERE account_id=%s", [
            account_id
        ]
        if selection is not None:
            sql += " AND uid=ANY(%s)"
            args.append(list(selection))
        else:
            sql += " AND retrieved_at IS NULL"
            if monster is not None:
                sql += " AND monster_uid=%s"
                args.append(monster)
        rows = list(db.execute(sql + " ORDER BY uid FOR UPDATE", args))
        if selection is not None and len(rows) != len(selection):
            raise ValueError("Missing or foreign native reward selection")
        pending = [row for row in rows if row["retrieved_at"] is None]
        current = store.character(account_id, recipient, db)
        packets = []
        if pending:
            if selection is not None:
                packets = _target_grant(
                    store, db, account_id, generation, current, pending, bag, slot
                )
            else:
                products = {}
                for row in pending:
                    products[row["item_ref"]] = (
                        products.get(row["item_ref"], 0) + row["quantity"]
                    )
                packets = grant_outputs(
                    store, db, account_id, generation, current, products
                )["packets"]
            db.execute(
                "UPDATE account_ranch_rewards SET retrieved_at=%s,recipient_character_id=%s "
                "WHERE uid=ANY(%s) AND account_id=%s",
                (store.now(), recipient, [row["uid"] for row in pending], account_id),
            )
        # A successful commit can outlive its acknowledgement. Reconcile from
        # the durable complete ledger even on a no-op retry, including old
        # retrieved rows and new pending rewards produced for other creatures.
        # Reconciliation never calls the inventory delivery path again.
        ledger = records(db, account_id)
        packets.extend(
            changed(character["map_id"], ledger[start : start + 32767])
            for start in range(0, len(ledger), 32767)
        )
        if not ledger:
            packets.append(changed(character["map_id"], []))
        return dict(
            character=store.character(account_id, recipient, db),
            packets=packets,
            applied=bool(pending),
            reward_uids=[row["uid"] for row in pending],
            recipient_character_id=recipient,
        )
