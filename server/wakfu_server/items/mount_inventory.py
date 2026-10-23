"""Persist mount state per owned UID, without resetting existing units."""
from psycopg.pq import TransactionStatus


def initialize(db, uid, character_id, now):
    """Called within the grant/equipment transaction after its lease check."""
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Mount initialization requires a transaction")
    if (
        type(uid) is not int
        or uid <= 0
        or type(character_id) is not int
        or character_id <= 0
    ):
        raise ValueError("Invalid mount owner")
    item = db.execute(
        "SELECT * FROM inventory_items WHERE uid=%s AND character_id=%s FOR UPDATE",
        (uid, character_id),
    ).fetchone()
    if item is None or item["quantity"] != 1:
        raise ValueError("Mount requires an owned, unstacked unit")
    model = db.execute(
        "SELECT * FROM mount_models WHERE reference=%s", (item["reference"],)
    ).fetchone()
    if model is None:
        raise ValueError("Missing verified mount model")
    timestamp = int(now.timestamp()) * 1000
    if timestamp <= 0:
        raise ValueError("Invalid mount creation clock")
    db.execute(
        "INSERT INTO inventory_mounts(uid,model_id,health,last_meal_date,last_hungry_date) "
        "VALUES(%s,%s,%s,%s,%s) ON CONFLICT(uid) DO NOTHING",
        (uid, model["model_id"], model["maximum_health"], timestamp, timestamp),
    )
    state = db.execute("SELECT * FROM inventory_mounts WHERE uid=%s", (uid,)).fetchone()
    if state["model_id"] != model["model_id"]:
        raise ValueError("Mount definition differs from the owned item")
    return dict(
        state,
        definition_id=state["model_id"],
        daily_limit_enabled=daily_limit_enabled(db),
    )


def daily_limit_enabled(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='pet_feeding_daily_limit_enabled'"
    ).fetchone()
    value = True if row is None else row["value"]
    if type(value) is not bool:
        raise ValueError("Invalid pet feeding daily-limit policy")
    return value


def hydrate(db, items):
    """One query for the collection; absent mount state is never synthesized."""
    if not items:
        return items
    states = {
        row["uid"]: dict(row, definition_id=row["model_id"])
        for row in db.execute(
            "SELECT *,COALESCE((SELECT value FROM settings "
            "WHERE name='pet_feeding_daily_limit_enabled'),'true'::jsonb) "
            "AS daily_limit_enabled FROM inventory_mounts WHERE uid=ANY(%s)",
            ([item["uid"] for item in items],),
        )
    }
    if any(type(state["daily_limit_enabled"]) is not bool for state in states.values()):
        raise ValueError("Invalid pet feeding daily-limit policy")
    return [
        dict(item, mount=states[item["uid"]]) if item["uid"] in states else item
        for item in items
    ]


def equipped(character):
    """Resolve the mount unit through the authoritative active equipment sheet."""
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.builds import valid_index, effective_sheet_level

    index = character.get("active_build_index", 0)
    if not valid_index(index):
        raise ValueError("Invalid active mount equipment sheet")
    saved = character.get("builds", {}).get(index, {})
    blob = bytes.fromhex(saved.get("equipment", ""))
    level = effective_sheet_level(character, index)
    selected = validate_sheet(
        dict(
            character,
            real_level=character.get("real_level", character["level"]),
            level=level,
            effective_level=level,
        ),
        blob,
        strict=False,
    )
    units = {item["uid"]: item for item in character.get("inventory_items", [])}
    for entry in selected:
        if entry["slot"] == 24:
            unit = units[entry["uid"]]
            state = unit.get("mount")
            if state is None:
                raise ValueError("Equipped mount has no authoritative unit state")
            return unit
    return None


def actor_pet(character):
    """Publish independent original companion and mount records in rw order."""
    from .mount_codec import pet_section
    from .pet_inventory import actor_pet as companion_pet

    companion = companion_pet(character)
    unit = equipped(character)
    if unit is None:
        return companion + b"\x00"
    state = unit["mount"]
    record = character.get("owned_cosmetics")
    if record is not None:
        from wakfu_server.characters.cosmetics import OwnedCosmetics

        owned = OwnedCosmetics.from_record(
            record, account_id=character.get("account_id")
        )
        reference = owned.selected_single(character["id"], 1)
        if reference:
            _, _, color, accessory = next(
                row for row in owned.items if row[:2] == (1, reference)
            )
            # Native eSP.a/b project appearance operands, not the mount definition.
            # Zero accessory is encoded absent in fC and falls back to its item ref.
            state = dict(
                state, color_item_ref=color, equipped_item_ref=accessory or reference
            )
    return companion + pet_section(state)[1:]
