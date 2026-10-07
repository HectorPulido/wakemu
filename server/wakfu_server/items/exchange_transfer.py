"""Plan and apply a bilateral inventory transfer inside the owner's SQL locks.

Capacity is calculated after both outgoing offers, permitting a swap between
two full inventories. Whole units keep UID; splits use the shared allocator.
Only identical native stack metadata can merge. No client slots are trusted.
"""
from copy import deepcopy
from psycopg import sql
from .inventory_move import STACKS


def _same_stack(first, second):
    rule = STACKS.get(first["reference"])
    return (
        rule is not None
        and rule["minimal_mergeable"]
        and first["reference"] == second["reference"]
        and "mount" not in first
        and "mount" not in second
        and first.get("shard_state") is None
        and second.get("shard_state") is None
        and all(
            first.get(key) == second.get(key)
            for key in ("damage_elements", "resistance_elements", "bound")
        )
    )


def plan(items, containers, offers, *, allocate, excluded_uids=()):
    """Pure final-state plan; allocate() supplies a unique split identity."""
    original = {item["uid"]: deepcopy(item) for item in items}
    if len(original) != len(items):
        raise ValueError("Duplicate inventory identity")
    final = deepcopy(original)
    owners = sorted({bag["character_id"] for bag in containers})
    if len(owners) != 2:
        raise ValueError("Exchange needs two inventory owners")
    offered = set()
    incoming = []
    for offer in sorted(offers, key=lambda entry: entry["uid"]):
        uid, quantity, owner = offer["uid"], offer["quantity"], offer["character_id"]
        source = original.get(uid)
        if (
            uid in offered
            or source is None
            or source["character_id"] != owner
            or owner not in owners
            or type(quantity) is not int
            or not 1 <= quantity <= source["quantity"]
        ):
            raise ValueError("Invalid owned exchange transfer")
        offered.add(uid)
        unit = deepcopy(source)
        unit["quantity"] = quantity
        unit["character_id"] = next(
            identity for identity in owners if identity != owner
        )
        if quantity == source["quantity"]:
            del final[uid]
        else:
            if "mount" in source or source.get("shard_state") is not None:
                raise ValueError("Mount or socketed item cannot be split")
            final[uid]["quantity"] -= quantity
            unit["uid"] = allocate()
            unit["split_source_uid"] = uid
            if (
                type(unit["uid"]) is not int
                or not 0 < unit["uid"] < 2**63
                or unit["uid"] in original
                or any(row[1]["uid"] == unit["uid"] for row in incoming)
            ):
                raise ValueError("Invalid allocated exchange unit identity")
        incoming.append((uid, unit))
    movements = []
    for source_uid, unit in incoming:
        rule = STACKS.get(unit["reference"])
        if rule is None or not 1 <= unit["quantity"] <= rule["maximum"]:
            raise ValueError("Unsupported incoming exchange stack")
        remaining = unit["quantity"]
        for target in sorted(final.values(), key=lambda entry: entry["uid"]):
            if (
                target["character_id"] != unit["character_id"]
                or target["uid"] in excluded_uids
                or not _same_stack(unit, target)
            ):
                continue
            moved = min(remaining, rule["maximum"] - target["quantity"])
            if moved <= 0:
                continue
            target["quantity"] += moved
            remaining -= moved
            movements.append(
                dict(
                    source_uid=source_uid,
                    received_uid=target["uid"],
                    character_id=target["character_id"],
                    quantity=moved,
                )
            )
            if not remaining:
                break
        if not remaining:
            continue
        destination = None
        for bag in sorted(containers, key=lambda entry: (entry["kind"], entry["uid"])):
            if bag["character_id"] != unit["character_id"] or bag["kind"] not in (
                0,
                1,
                2,
                3,
            ):
                continue
            occupied = {
                row["slot"] for row in final.values() if row["container"] == bag["uid"]
            }
            slot = next(
                (index for index in range(bag["capacity"]) if index not in occupied),
                None,
            )
            if slot is not None:
                destination = (bag["uid"], slot)
                break
        if destination is None:
            raise ValueError("Exchange recipient inventory is full")
        unit.update(container=destination[0], slot=destination[1], quantity=remaining)
        final[unit["uid"]] = unit
        movements.append(
            dict(
                source_uid=source_uid,
                received_uid=unit["uid"],
                character_id=unit["character_id"],
                quantity=remaining,
            )
        )
    return final, movements


def apply(db, original, final):
    """Preserve all current UID metadata, including when whole units change owner.

    Remove outgoing full rows first to free both inventories' unique slots.
    Their metadata is captured before cascading deletion and restored exactly;
    split units copy it to the allocated UID without rerolling or reinitializing.
    """
    by_uid = {row["uid"]: row for row in original}
    metadata = {}
    for table in (
        "inventory_item_elements",
        "inventory_item_shards",
        "inventory_item_bindings",
        "inventory_mounts",
    ):
        metadata[table] = {
            row["uid"]: dict(row)
            for row in db.execute(
                sql.SQL(
                    "SELECT * FROM {} WHERE uid=ANY(%s) ORDER BY uid FOR UPDATE"
                ).format(sql.Identifier(table)),
                (list(by_uid),),
            )
        }
    removed = [
        uid
        for uid, row in by_uid.items()
        if uid not in final or final[uid]["character_id"] != row["character_id"]
    ]
    if removed:
        db.execute("DELETE FROM inventory_items WHERE uid=ANY(%s)", (removed,))
    fields = ("uid", "character_id", "reference", "quantity", "container", "slot")
    for uid, row in sorted(final.items()):
        previous = by_uid.get(uid)
        if previous is not None and uid not in removed:
            if row["quantity"] != previous["quantity"]:
                db.execute(
                    "UPDATE inventory_items SET quantity=%s WHERE uid=%s",
                    (row["quantity"], uid),
                )
            continue
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            tuple(row[key] for key in fields),
        )
        source_uid = row.get("split_source_uid", uid)
        for table, records in metadata.items():
            record = records.get(source_uid)
            if record is None:
                continue
            copied = dict(record, uid=uid)
            columns = list(copied)
            db.execute(
                sql.SQL("INSERT INTO {} ({}) VALUES ({})").format(
                    sql.Identifier(table),
                    sql.SQL(",").join(map(sql.Identifier, columns)),
                    sql.SQL(",").join(sql.Placeholder() for column in columns),
                ),
                tuple(copied[column] for column in columns),
            )
