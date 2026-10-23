"""Native pet sleep state with an explicit, finite Wakemu wake policy.

The client supplies the allowed food, seven-day period, sleeping predicate and
clear-state messages. Server expiry at that deadline and shifting both hunger
baselines by the sleeping interval are Wakemu lifecycle policy, not recovered
original server code. Pure projections never checkpoint or acquire row locks.
"""
import struct
from hashlib import sha256


def clock_ms(now):
    if now.tzinfo is None:
        raise ValueError("Pet hibernation requires a timezone-aware clock")
    value = int(now.timestamp() * 1000)
    if value <= 0:
        raise ValueError("Invalid pet hibernation clock")
    return value


def sleeping(state):
    """Original fvN.gpM: a nonempty sleep date and a positive food reference."""
    return state.get("sleep_item_ref", 0) > 0 and state.get("sleep_date", 0) > 0


def active(state):
    """Original fvN.aqb/fnM.cA: healthy, awake pets can equip/apply bonuses."""
    return state.get("health", 0) > 0 and not sleeping(state)


def effective_state(state, now_ms):
    """Project a due wake without mutating persisted state or its revision."""
    if not sleeping(state):
        return state
    duration = state.get("sleep_duration_ms")
    if type(duration) is not int or duration <= 0:
        raise ValueError("Sleeping pet has no verified native duration")
    if now_ms < state["sleep_date"] + duration:
        return state
    result = dict(state)
    for key in ("last_meal_date", "last_hungry_date"):
        baseline = state[key]
        result[key] = baseline + duration if baseline > 0 else baseline
    result.update(sleep_item_ref=0, sleep_date=0)
    return result


def project_items(items, *, now_ms):
    result = []
    for item in items:
        state = effective_state(item["pet"], now_ms) if "pet" in item else None
        result.append(
            dict(item, pet=state)
            if state is not None and state is not item["pet"]
            else item
        )
    return result


def catch_up(db, character_id, *, now_ms, pet_uid=None):
    """Checkpoint only due, owned rows inside the caller's fenced transaction."""
    rows = list(
        db.execute(
            "SELECT p.*,s.duration_ms AS sleep_duration_ms FROM inventory_pets p "
            "JOIN inventory_items i ON i.uid=p.uid "
            "JOIN native_pet_hibernation_food_policy s "
            "ON s.model_id=p.model_id AND s.item_ref=p.sleep_item_ref "
            "WHERE i.character_id=%s AND p.sleep_date>0 "
            "AND p.sleep_date+s.duration_ms<=%s "
            "AND (%s::bigint IS NULL OR p.uid=%s) ORDER BY p.uid FOR UPDATE OF p",
            (character_id, now_ms, pet_uid, pet_uid),
        )
    )
    for row in rows:
        after = effective_state(row, now_ms)
        db.execute(
            "UPDATE inventory_pets SET sleep_item_ref=0,sleep_date=0,"
            "last_meal_date=%s,last_hungry_date=%s,revision=revision+1 WHERE uid=%s",
            (after["last_meal_date"], after["last_hungry_date"], row["uid"]),
        )
    return tuple(row["uid"] for row in rows)


def next_deadline(db, character_id):
    row = db.execute(
        "SELECT min(p.sleep_date+s.duration_ms) AS deadline FROM inventory_pets p "
        "JOIN inventory_items i ON i.uid=p.uid "
        "JOIN native_pet_hibernation_food_policy s "
        "ON s.model_id=p.model_id AND s.item_ref=p.sleep_item_ref "
        "WHERE i.character_id=%s AND p.sleep_date>0",
        (character_id,),
    ).fetchone()
    return row["deadline"]


def refresh(store, account_id, generation, character_id):
    """Login/tick catch-up; callers schedule again only at next_deadline_ms."""
    now_ms = clock_ms(store.now())
    with store.connection() as db:
        deadline = next_deadline(db, character_id)
        if deadline is None or deadline > now_ms:
            return dict(changed=False, packets=[], next_deadline_ms=deadline)
        from wakfu_server.inventory_owner import lock_inventory_character

        lock_inventory_character(store, db, account_id, generation, character_id)
        if db.execute(
            "SELECT 1 FROM combat_fight_participants p JOIN combat_fights f "
            "ON f.id=p.fight_id WHERE p.character_id=%s "
            "AND f.status IN ('placement','active') LIMIT 1",
            (character_id,),
        ).fetchone():
            # The live combat snapshot retains its admitted pet bonuses.
            return dict(changed=False, packets=[], next_deadline_ms=now_ms + 1000)
        changed = catch_up(db, character_id, now_ms=now_ms)
        if not changed:
            return dict(
                changed=False,
                packets=[],
                next_deadline_ms=next_deadline(db, character_id),
            )
        from wakfu_server.pet_feeding import _reconfigure_health
        from wakfu_server.inventory_items import insertion, equipment_inventory
        from wakfu_server.mount_feeding_wire import remove_delta

        character = _reconfigure_health(
            store, db, store.character(account_id, character_id, db)
        )
        owned = {row["uid"]: row for row in character["inventory_items"]}
        packets = [
            packet
            for uid in changed
            for packet in (remove_delta(uid, 1), insertion(owned[uid]))
        ]
        packets.append(equipment_inventory(character))
        return dict(
            changed=True,
            character=character,
            packets=packets,
            next_deadline_ms=next_deadline(db, character_id),
        )


def try_start(store, db, account_id, character_id, request, pet, item, food, now_ms):
    """Return a sleep result, or None for a non-hibernation food reference."""
    policy = db.execute(
        "SELECT * FROM native_pet_hibernation_food_policy WHERE model_id=%s AND item_ref=%s",
        (pet["model_id"], food["reference"]),
    ).fetchone()
    if policy is None:
        return None
    if request["quantity"] != 1:
        raise ValueError("Pet hibernation requires exactly one food unit")
    if sleeping(pet) or pet["sleep_item_ref"] > 0 or pet["sleep_date"] > 0:
        raise ValueError("Pet is already hibernating")
    from wakfu_server.simple_item_actions import _equipped, _idle

    character = store.character(account_id, character_id, db)
    _idle(db, character_id, store.now())
    if _equipped(character, food["uid"]):
        raise ValueError("Unequip the pet food source first")
    for table in (
        "inventory_item_elements",
        "inventory_item_shards",
        "inventory_mounts",
        "inventory_pets",
    ):
        if db.execute(f"SELECT 1 FROM {table} WHERE uid=%s", (food["uid"],)).fetchone():
            raise ValueError("Pet food has unsupported specific data")
    revision = pet["revision"] + 1
    db.execute(
        "UPDATE inventory_pets SET sleep_item_ref=%s,sleep_date=%s,revision=%s WHERE uid=%s",
        (food["reference"], now_ms, revision, item["uid"]),
    )
    if food["quantity"] == 1:
        db.execute("DELETE FROM inventory_items WHERE uid=%s", (food["uid"],))
    else:
        db.execute(
            "UPDATE inventory_items SET quantity=quantity-1 WHERE uid=%s",
            (food["uid"],),
        )
    from wakfu_server.pet_feeding import _reconfigure_health
    from wakfu_server.mount_feeding_wire import publication_packets
    from wakfu_server.inventory_items import equipment_inventory

    character = _reconfigure_health(
        store, db, store.character(account_id, character_id, db)
    )
    updated = next(
        row for row in character["inventory_items"] if row["uid"] == item["uid"]
    )
    digest = sha256(
        struct.pack(">qqi", item["uid"], food["uid"], request["quantity"])
    ).digest()
    receipt = db.execute(
        "INSERT INTO pet_hibernation_receipts(account_id,character_id,pet_uid,food_uid,"
        "request_sha256,after_revision,applied_at_ms,wakes_at_ms) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            account_id,
            character_id,
            item["uid"],
            food["uid"],
            digest,
            revision,
            now_ms,
            now_ms + policy["duration_ms"],
        ),
    ).fetchone()
    return dict(
        character=character,
        packets=[
            *publication_packets(dict(food), updated, 1),
            equipment_inventory(character),
        ],
        applied=True,
        replayed=False,
        receipt=dict(receipt),
        xp_delta=0,
        health_delta=0,
        next_deadline_ms=receipt["wakes_at_ms"],
    )


def validate_equipment_change(character, previous_blob, selected):
    """Existing sleeping units may remain stored; newly equipping them fails."""
    from wakfu_server.wire import proto_fields

    previous = {
        dict(proto_fields(value)).get(8)
        for tag, value in proto_fields(previous_blob)
        if tag == 10 and isinstance(value, bytes)
    }
    owned = {row["uid"]: row for row in character.get("inventory_items", [])}
    for row in selected:
        item = owned[row["uid"]]
        if row["uid"] not in previous and "pet" in item and not active(item["pet"]):
            raise ValueError("An unhealthy or sleeping native pet cannot be equipped")
