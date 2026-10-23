"""Native companion-pet diets through the explicit 12767 target request."""
from datetime import datetime, timezone
from hashlib import sha256
import struct


def apply_if_pet(store, db, account_id, generation, character_id, request):
    """Run inside the feeding caller's already owner-locked transaction."""
    pet = db.execute(
        "SELECT p.*,m.reference AS model_reference,m.maximum_health,m.xp_per_level,"
        "m.maximum_level,m.xp_item_refs FROM inventory_pets p "
        "JOIN native_pet_models m USING(model_id) WHERE p.uid=%s FOR UPDATE OF p",
        (request["pet_uid"],),
    ).fetchone()
    if pet is None:
        return None
    item = db.execute(
        "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
        "WHERE i.uid=%s AND i.character_id=%s AND c.character_id=%s FOR UPDATE OF i",
        (request["pet_uid"], character_id, character_id),
    ).fetchone()
    if (
        item is None
        or item["quantity"] != 1
        or item["reference"] != pet["model_reference"]
    ):
        raise ValueError("Pet target is unavailable or not a singleton owned unit")
    now = store.now()
    if now.tzinfo is None:
        raise ValueError("Pet feeding requires a timezone-aware clock")
    now_ms = int(now.timestamp()) * 1000
    from wakfu_server.pet_hibernation import catch_up, try_start

    if catch_up(db, character_id, now_ms=now_ms, pet_uid=pet["uid"]):
        pet = dict(
            pet,
            **db.execute(
                "SELECT * FROM inventory_pets WHERE uid=%s", (pet["uid"],)
            ).fetchone(),
        )
    digest = sha256(
        struct.pack(
            ">qqi", request["pet_uid"], request["food_uid"], request["quantity"]
        )
    ).digest()
    sleep_receipt = db.execute(
        "SELECT * FROM pet_hibernation_receipts WHERE pet_uid=%s AND request_sha256=%s "
        "ORDER BY after_revision DESC LIMIT 1",
        (item["uid"], digest),
    ).fetchone()
    if (
        sleep_receipt is not None
        and sleep_receipt["account_id"] == account_id
        and sleep_receipt["character_id"] == character_id
        and sleep_receipt["after_revision"] == pet["revision"]
        and pet["sleep_date"] == sleep_receipt["applied_at_ms"]
        and 0 <= now_ms - sleep_receipt["applied_at_ms"] < 3000
    ):
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[],
            applied=False,
            replayed=True,
            receipt=dict(sleep_receipt),
            xp_delta=0,
            health_delta=0,
            next_deadline_ms=sleep_receipt["wakes_at_ms"],
        )
    previous = db.execute(
        "SELECT * FROM pet_feeding_receipts WHERE pet_uid=%s AND request_sha256=%s "
        "ORDER BY after_revision DESC LIMIT 1",
        (item["uid"], digest),
    ).fetchone()
    if (
        previous is not None
        and previous["account_id"] == account_id
        and previous["character_id"] == character_id
        and previous["after_revision"] == pet["revision"]
        and pet["last_meal_date"] == previous["applied_at_ms"]
        and 0 <= now_ms - previous["applied_at_ms"] < 3000
    ):
        return dict(
            character=store.character(account_id, character_id, db),
            packets=[],
            applied=False,
            replayed=True,
            receipt=dict(previous),
            xp_delta=previous["xp_delta"],
            health_delta=previous["health_delta"],
        )
    food = db.execute(
        "SELECT i.* FROM inventory_items i JOIN inventory_containers c ON c.uid=i.container "
        "WHERE i.uid=%s AND i.character_id=%s AND c.character_id=%s FOR UPDATE OF i",
        (request["food_uid"], character_id, character_id),
    ).fetchone()
    if food is None or food["quantity"] < request["quantity"]:
        raise ValueError("Pet food is unavailable or exceeds the owned stack")
    hibernation = try_start(
        store, db, account_id, character_id, request, pet, item, food, now_ms
    )
    if hibernation is not None:
        return hibernation
    policy = db.execute(
        "SELECT * FROM native_pet_feeding_food_policy WHERE model_id=%s AND item_ref=%s",
        (pet["model_id"], food["reference"]),
    ).fetchone()
    if policy is None:
        raise ValueError("Food is not eligible for this native pet model")
    if policy["action_id"] is not None:
        # Level foods retain their separate native bHX calculation. Ordinary
        # diets do not execute the food item's unrelated world-use action.
        rule = db.execute(
            "SELECT * FROM native_pet_xp_actions WHERE item_ref=%s",
            (food["reference"],),
        ).fetchone()
        from wakfu_server.haven_bag_furniture_knowledge import _rules

        native = _rules().get(food["reference"])
        if (
            rule is None
            or rule["has_criteria"]
            or native is None
            or native.get("use_action_class") != "bHX"
            or native.get("use_action_id") != rule["action_id"]
            or rule["action_id"] != policy["action_id"]
            or food["reference"] not in pet["xp_item_refs"]
            or policy["xp_per_item"] != rule["levels"] * pet["xp_per_level"]
        ):
            raise ValueError("Food is not an eligible native pet level action")
    if pet["sleep_item_ref"] > 0 or pet["sleep_date"] > 0:
        raise ValueError("Feeding a sleeping pet is unsupported")
    from wakfu_server.mount_inventory import daily_limit_enabled

    if (
        policy["effect_kind"] == "xp"
        and daily_limit_enabled(db)
        and pet["last_meal_date"] > 0
        and datetime.fromtimestamp(pet["last_meal_date"] / 1000, timezone.utc).date()
        == now.astimezone(timezone.utc).date()
    ):
        raise ValueError("Pet XP food is limited to once per UTC calendar day")
    after_xp, after_health = pet["xp"], pet["health"]
    xp_delta = health_delta = 0
    if policy["effect_kind"] == "xp":
        maximum = pet["xp_per_level"] * pet["maximum_level"]
        amount = policy["xp_per_item"] * request["quantity"]
        after_xp = min(maximum, pet["xp"] + amount)
        xp_delta = after_xp - pet["xp"]
        if xp_delta <= 0:
            raise ValueError("Pet is already at maximum XP")
    elif policy["effect_kind"] == "heal":
        amount = policy["health_per_item"]
        missing = pet["maximum_health"] - pet["health"]
        if amount <= 0 or missing <= 0:
            raise ValueError("Pet health food has no applicable effect")
        if request["quantity"] > (missing + amount - 1) // amount:
            raise ValueError("Requested pet health food exceeds missing health")
        after_health = min(
            pet["maximum_health"], pet["health"] + amount * request["quantity"]
        )
        health_delta = after_health - pet["health"]
    else:
        raise ValueError("Unsupported native pet food effect")
    from wakfu_server.simple_item_actions import _equipped, _idle

    character = store.character(account_id, character_id, db)
    _idle(db, character_id, now)
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
        "UPDATE inventory_pets SET xp=%s,health=%s,last_meal_date=%s,revision=%s WHERE uid=%s",
        (after_xp, after_health, now_ms, revision, item["uid"]),
    )
    if food["quantity"] == request["quantity"]:
        db.execute("DELETE FROM inventory_items WHERE uid=%s", (food["uid"],))
    else:
        db.execute(
            "UPDATE inventory_items SET quantity=quantity-%s WHERE uid=%s",
            (request["quantity"], food["uid"]),
        )
    character = store.character(account_id, character_id, db)
    from wakfu_server.pet_inventory import equipped

    selected = equipped(character)
    if selected is not None and selected["uid"] == item["uid"]:
        character = _reconfigure_health(store, db, character)
    updated = next(
        row for row in character["inventory_items"] if row["uid"] == item["uid"]
    )
    if updated.get("pet", {}).get("revision") != revision:
        raise ValueError("Pet publication disagrees with committed feeding state")
    from wakfu_server.mount_feeding_wire import publication_packets
    from wakfu_server.inventory_items import equipment_inventory

    packets = publication_packets(dict(food), updated, request["quantity"])
    packets.append(equipment_inventory(character))
    receipt = db.execute(
        "INSERT INTO pet_feeding_receipts(account_id,character_id,pet_uid,food_uid,quantity,"
        "request_sha256,after_revision,applied_at_ms,xp_delta,health_delta,effect_kind) "
        "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (
            account_id,
            character_id,
            item["uid"],
            food["uid"],
            request["quantity"],
            digest,
            revision,
            now_ms,
            xp_delta,
            health_delta,
            policy["effect_kind"],
        ),
    ).fetchone()
    return dict(
        character=character,
        packets=packets,
        applied=True,
        replayed=False,
        receipt=dict(receipt),
        xp_delta=xp_delta,
        health_delta=health_delta,
    )


def _reconfigure_health(store, db, character):
    """Pet progression changes configuration, never canonical wounds or death."""
    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.health_policy import reconfigure

    maximum = effective_character(character, include_consumable_buffs=True)["max_hp"]
    if maximum == character["max_hp"]:
        return character
    hp = reconfigure(db, character, maximum)
    now = store.now()
    db.execute(
        "INSERT INTO character_regeneration"
        "(character_id,initial_hp,started_at,last_at,coefficient) VALUES(%s,%s,%s,%s,0) "
        "ON CONFLICT(character_id) DO UPDATE SET initial_hp=excluded.initial_hp,"
        "started_at=excluded.started_at,last_at=excluded.last_at,"
        "coefficient=CASE WHEN excluded.initial_hp=0 THEN 0 "
        "ELSE character_regeneration.coefficient END",
        (character["id"], hp, now, now),
    )
    return dict(character, hp=hp, max_hp=maximum)
