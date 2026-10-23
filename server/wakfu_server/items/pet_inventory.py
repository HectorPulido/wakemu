"""Companion-pet authority per owned UID, separate from mount model IDs."""
from psycopg.pq import TransactionStatus


def _state(row):
    return dict(row, definition_id=row["model_id"])


def initialize(db, uid, character_id, now):
    """Create a new singleton's state without resetting an existing companion."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Pet initialization requires a transaction")
    if (
        type(uid) is not int
        or uid <= 0
        or type(character_id) is not int
        or character_id <= 0
    ):
        raise ValueError("Invalid companion pet owner")
    item = db.execute(
        "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
        (uid, character_id),
    ).fetchone()
    if item is None or item["quantity"] != 1:
        raise ValueError("Pet requires an owned unstacked unit")
    model = db.execute(
        "SELECT * FROM native_pet_models WHERE reference=%s", (item["reference"],)
    ).fetchone()
    if model is None:
        raise ValueError("Missing verified companion pet model")
    if now.tzinfo is None:
        raise ValueError("Pet creation clock must be timezone-aware")
    timestamp = int(now.timestamp()) * 1000
    if timestamp <= 0:
        raise ValueError("Invalid pet creation clock")
    db.execute(
        "INSERT INTO inventory_pets(uid,model_id,health,equipped_item_ref,last_meal_date,last_hungry_date) VALUES(%s,%s,%s,%s,%s,%s) ON CONFLICT(uid) DO NOTHING",
        (
            uid,
            model["model_id"],
            model["maximum_health"],
            model["default_equipped_item_ref"],
            timestamp,
            timestamp,
        ),
    )
    state = db.execute("SELECT * FROM inventory_pets WHERE uid=%s", (uid,)).fetchone()
    if state["model_id"] != model["model_id"]:
        raise ValueError("Pet definition differs from its owned item")
    from .mount_inventory import daily_limit_enabled

    return _state(
        dict(
            state,
            xp_per_level=model["xp_per_level"],
            maximum_level=model["maximum_level"],
            maximum_health=model["maximum_health"],
            daily_limit_enabled=daily_limit_enabled(db),
        )
    )


def hydrate(db, items):
    """Batch-load only existing companion authority; reads never initialize it."""
    if not items:
        return items
    states = {
        row["uid"]: _state(row)
        for row in db.execute(
            "SELECT p.*,model.xp_per_level,model.maximum_level,model.maximum_health,"
            "sleep.duration_ms AS sleep_duration_ms,"
            "COALESCE((SELECT value FROM settings WHERE name='pet_feeding_daily_limit_enabled'),'true'::jsonb) AS daily_limit_enabled "
            "FROM inventory_pets p JOIN native_pet_models model USING(model_id) "
            "LEFT JOIN native_pet_hibernation_food_policy sleep "
            "ON sleep.model_id=p.model_id AND sleep.item_ref=p.sleep_item_ref "
            "WHERE p.uid=ANY(%s)",
            ([item["uid"] for item in items],),
        )
    }
    if any(type(row["daily_limit_enabled"]) is not bool for row in states.values()):
        raise ValueError("Invalid pet feeding daily-limit policy")
    if any("mount" in item and item["uid"] in states for item in items):
        raise ValueError("One unit cannot be both a pet and a mount")
    return [
        dict(item, pet=states[item["uid"]]) if item["uid"] in states else item
        for item in items
    ]


def equipped(character):
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.builds import valid_index, effective_sheet_level

    index = character.get("active_build_index", 0)
    if not valid_index(index):
        raise ValueError("Invalid active pet equipment sheet")
    saved = character.get("builds", {}).get(index, {})
    level = effective_sheet_level(character, index)
    selected = validate_sheet(
        dict(
            character,
            real_level=character.get("real_level", character["level"]),
            level=level,
            effective_level=level,
        ),
        bytes.fromhex(saved.get("equipment", "")),
        strict=False,
    )
    units = {item["uid"]: item for item in character.get("inventory_items", [])}
    for entry in selected:
        if entry["slot"] == 22:
            unit = units[entry["uid"]]
            if "pet" not in unit:
                raise ValueError("Equipped pet has no authoritative companion state")
            return unit
    return None


def actor_pet(character):
    from .pet_codec import companion_section

    unit = equipped(character)
    if unit is None:
        return companion_section(None)
    state = unit["pet"]
    record = character.get("owned_cosmetics")
    if record is not None:
        from wakfu_server.characters.cosmetics import OwnedCosmetics

        owned = OwnedCosmetics.from_record(
            record, account_id=character.get("account_id")
        )
        reference = owned.selected_single(character["id"], 2)
        if reference:
            _, _, color, accessory = next(
                row for row in owned.items if row[:2] == (2, reference)
            )
            state = dict(
                state, color_item_ref=color, equipped_item_ref=accessory or reference
            )
    return companion_section(state)
