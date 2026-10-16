"""Native achievement rewards inside a caller-owned, authorized transaction.

The caller locks account before character and owns replay protection, savepoints,
commit and publication. Capacity errors do not mutate inventory. Item rewards preflight all eligible bags and merge only identical plain stacks.
"""
from psycopg.pq import TransactionStatus


class RewardCapacity(ValueError):
    """The native reward fits no eligible inventory capacity; retry later."""


def validate(reward):
    """Validate the installed aJP representation without coercing native values."""
    if not isinstance(reward, dict):
        raise ValueError("Invalid achievement reward")
    kind, parameters = reward.get("aeV"), reward.get("ckl")
    if type(kind) is not int or kind not in (2, 3, 5, 6):
        raise ValueError("Unsupported native achievement reward")
    if not isinstance(parameters, (list, tuple)) or len(parameters) != (
        2 if kind == 5 else 1
    ):
        raise ValueError("Invalid native achievement reward arity")
    if any(type(value) is not int or not 0 < value < (1 << 31) for value in parameters):
        raise ValueError("Invalid native achievement reward parameters")
    if kind == 2 and parameters[0] > 65535:
        raise ValueError("Native title identity exceeds unsigned16")
    return kind, tuple(parameters)


def grant(db, store, character, reward):
    """Grant one qualified aJP reward and return native publication packets.

    Only the qualified catalog should call this function. The caller authorizes
    the durable participant, including offline heroes. No selected-session
    requirement is imposed on earned settlement rewards. After draining pending
    rewards at login, reload the character before building its absolute XP,
    inventory and journal bootstrap. XP delta packets precede absolute XP state.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Achievement rewards require an active transaction")
    kind, parameters = validate(reward)
    if kind == 2:
        return _title(db, character, parameters[0])
    if kind == 3:
        return _emote(db, character, parameters[0])
    if kind == 6:
        return _xp(db, store, character, parameters[0])
    return _item(db, store, character, *parameters)


def _item(db, store, character, reference, quantity):
    from wakfu_server.inventory_move import ACQUISITION_STACKS as STACKS
    from wakfu_server.inventory_uids import allocate
    from wakfu_server.inventory_elements import create, save

    from wakfu_server.items import quest_inventory

    if reference in quest_inventory.REFERENCES:
        result = quest_inventory.grant(db, character["id"], reference, quantity)
        return [result["quest_packet"]]
    rule = STACKS.get(reference)
    if rule is None or type(rule.get("maximum")) is not int or rule["maximum"] < 1:
        raise ValueError("Missing native reward item stack rule")
    maximum = min(rule["maximum"], 32767)
    # Native mounts are individual units even when a catalog stack rule differs.
    is_mount = (
        db.execute(
            "SELECT 1 FROM mount_models WHERE reference=%s", (reference,)
        ).fetchone()
        is not None
    )
    if is_mount:
        maximum = 1
    from wakfu_server.combat_drop_delivery import (
        _binding_rows,
        _container_can_hold,
        _effective_bound,
        _equipped_uids,
        _save_binding,
        _template_bound,
        _item_proto,
    )
    from wakfu_server.inventory_elements import hydrate, masks
    import struct

    containers = [
        dict(row)
        for row in db.execute(
            "SELECT * FROM inventory_containers WHERE character_id=%s ORDER BY kind,uid FOR UPDATE",
            (character["id"],),
        ).fetchall()
    ]
    eligible = [bag for bag in containers if _container_can_hold(bag, character["id"])]
    items = hydrate(
        db,
        [
            dict(row)
            for row in db.execute(
                "SELECT * FROM inventory_items WHERE character_id=%s ORDER BY uid FOR UPDATE",
                (character["id"],),
            ).fetchall()
        ],
    )
    bindings = _binding_rows(db, items)
    excluded = _equipped_uids(store, character["account_id"], character["id"], db)
    excluded.update(
        row["uid"]
        for row in db.execute(
            "SELECT uid FROM inventory_item_shards WHERE uid=ANY(%s)",
            ([item["uid"] for item in items],),
        )
    )
    selection = create(reference)
    selected_masks = None if selection is None else masks(selection)
    bound = _template_bound(reference)
    eligible_ids = {bag["uid"] for bag in eligible}
    compatible = []
    for item in items:
        item["bound"] = bindings.get(item["uid"], False)
        if (
            not is_mount
            and rule["minimal_mergeable"]
            and item["container"] in eligible_ids
            and item["uid"] not in excluded
            and item["reference"] == reference
            and _effective_bound(item) == bound
            and masks(item) == selected_masks
        ):
            compatible.append(item)
    merges, placements = _plan_item_capacity(
        eligible, items, compatible, quantity, maximum
    )
    packets = []
    for item, amount in merges:
        db.execute(
            "UPDATE inventory_items SET quantity=quantity+%s WHERE uid=%s",
            (amount, item["uid"]),
        )
        packets.append((12470, struct.pack(">qh", item["uid"], amount)))
    for bag, slot, amount in placements:
        uid = allocate(db)
        db.execute(
            "INSERT INTO inventory_items(uid,character_id,reference,quantity,container,slot) "
            "VALUES(%s,%s,%s,%s,%s,%s)",
            (uid, character["id"], reference, amount, bag["uid"], slot),
        )
        item = dict(
            db.execute("SELECT * FROM inventory_items WHERE uid=%s", (uid,)).fetchone()
        )
        if selection is not None:
            save(db, uid, selection)
            item.update(selection)
        _save_binding(db, uid, reference, bound)
        item["bound"] = bound
        if is_mount:
            from wakfu_server.mount_inventory import initialize

            item["mount"] = initialize(db, uid, character["id"], store.now())
        proto = _item_proto(item)
        packets.append(
            (
                12471,
                struct.pack(">qhI", item["container"], item["slot"], len(proto))
                + proto
                + b"\x01",
            )
        )
    return packets


def _plan_item_capacity(containers, items, compatible, quantity, maximum):
    """Preflight the complete reward without allocating UIDs or mutating rows."""
    remaining = quantity
    merges, placements = [], []
    for item in compatible:
        amount = min(remaining, max(0, maximum - item["quantity"]))
        if amount:
            merges.append((item, amount))
            remaining -= amount
    occupied = {(item["container"], item["slot"]) for item in items}
    for bag in containers:
        for slot in range(bag["capacity"]):
            if remaining == 0:
                break
            if (bag["uid"], slot) in occupied:
                continue
            amount = min(remaining, maximum)
            placements.append((bag, slot, amount))
            remaining -= amount
    if remaining:
        raise RewardCapacity(
            "Insufficient eligible inventory capacity for achievement reward"
        )
    return merges, placements


def _title(db, character, title_id):
    from psycopg.types.json import Jsonb
    from wakfu_server.cosmetics import OwnedCosmetics
    from wakfu_server.cosmetic_store import load
    from wakfu_server.cosmetic_learning import snapshot

    record = load(db, character["account_id"])
    if record is None:
        raise ValueError("Missing account cosmetic schema")
    if any(row[:2] == (7, title_id) for row in record.items):
        return [snapshot(record)]
    record = OwnedCosmetics(
        record.account_id,
        record.items + ((7, title_id, 0, 0),),
        record.selections,
        record.inactive_characters,
        record.costumes,
        record.single_selections,
    )
    if character["id"] not in dict(record.selections):
        record = record.equip_finishers(character, ())
    db.execute(
        "INSERT INTO account_cosmetics(account_id,record) VALUES(%s,%s) "
        "ON CONFLICT(account_id) DO UPDATE SET record=EXCLUDED.record,"
        "revision=account_cosmetics.revision+1",
        (character["account_id"], Jsonb(record.to_record())),
    )
    return [snapshot(record)]


def _emote(db, character, emote_id):
    import struct
    from wakfu_server import emotes

    if not db.execute(
        "SELECT 1 FROM native_emote_definitions WHERE emote_id=%s", (emote_id,)
    ).fetchone():
        raise ValueError("Missing native achievement emote definition")
    created = db.execute(
        "INSERT INTO account_emote_knowledge(account_id,emote_id) VALUES(%s,%s) "
        "ON CONFLICT(account_id,emote_id) DO NOTHING RETURNING emote_id",
        (character["account_id"], emote_id),
    ).fetchone()
    packets = []
    if created is not None:
        packets.append((12266, struct.pack(">iB", emote_id, 1)))
    packets.append(emotes.snapshot(db, character["account_id"]))
    return packets


def _xp(db, store, character, amount):
    """Persist fixed earned XP; caller publishes final absolute state afterward.

    The native 13613 notification adds a delta. It must precede the settlement's
    final absolute progression snapshot; outbox replays must not grant again.
    """
    from wakfu_server.progression import XP_BY_LEVEL
    from wakfu_server.combat_rewards import _initialize_health_for_durable_member
    from wakfu_server.combat_xp_gain import notification

    # Reload after other rewards in this transaction instead of trusting an old
    # character argument (several achievements may cross a level boundary).
    current = store.character(character["account_id"], character["id"], db)
    row = db.execute(
        "SELECT xp FROM character_progression WHERE character_id=%s FOR UPDATE",
        (character["id"],),
    ).fetchone()
    if row is None or type(row["xp"]) is not int or row["xp"] < 0:
        raise ValueError("Missing authoritative achievement XP progression")
    total = row["xp"] + amount
    if total >= (1 << 63):
        raise ValueError("Achievement XP exceeds native signed64 storage")
    level = max(
        current["level"],
        max(value for value, threshold in XP_BY_LEVEL.items() if threshold <= total),
    )
    db.execute(
        "UPDATE character_progression SET xp=%s WHERE character_id=%s",
        (total, character["id"]),
    )
    db.execute(
        "UPDATE characters SET level=%s WHERE id=%s AND account_id=%s",
        (level, character["id"], character["account_id"]),
    )
    if level != current["level"]:
        _initialize_health_for_durable_member(
            store, db, character["account_id"], character["id"]
        )
    return [
        notification(
            character["id"],
            {
                "character": {"id": character["id"]},
                "awarded": True,
                "xp": amount,
                "xp_info": {
                    "won_xp": amount,
                    "end_xp": total,
                    "start_level": current["level"],
                    "end_level": level,
                },
            },
        )
    ]
