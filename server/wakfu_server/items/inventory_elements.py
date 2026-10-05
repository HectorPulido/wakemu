"""Persisted fnR.foX element selections, never rerolled by equipping.

foX.cL draws without replacement from FIRE/WATER/EARTH/AIR at creation.
kX.elements/le stores two masks; absence means foX=null and no eWe bonus.
"""
from random import SystemRandom

ELEMENTS = (1, 2, 3, 4)
FIELDS = {1068: "damage_elements", 1069: "resistance_elements"}
STATS = {1068: {1: 21, 2: 22, 3: 23, 4: 24}, 1069: {1: 28, 2: 29, 3: 30, 4: 31}}
VALID_MASK = sum(1 << element for element in ELEMENTS)


def schema(db):
    db.execute(
        """CREATE TABLE IF NOT EXISTS inventory_item_elements (
        uid INTEGER PRIMARY KEY REFERENCES inventory_items(uid) ON DELETE CASCADE,
        damage_elements INTEGER NOT NULL CHECK(damage_elements BETWEEN 0 AND 30),
        resistance_elements INTEGER NOT NULL CHECK(resistance_elements BETWEEN 0 AND 30))"""
    )


def masks(item):
    present = [field in item for field in FIELDS.values()]
    if not any(present):
        return None  # Actual kX.elements absent, fox.a sets fnR.foX=null.
    if not all(present):
        raise ValueError("Incomplete native element selection")
    values = tuple(item[field] for field in FIELDS.values())
    if any(
        type(value) is not int or value < 0 or value & ~VALID_MASK for value in values
    ):
        raise ValueError("Invalid native item element mask")
    return values


def create(reference, *, rng=None):
    from .equipment_stats import CATALOG

    item = CATALOG.get(reference)
    if item is None:
        return None
    selection = dict(damage_elements=0, resistance_elements=0)
    found = False
    for effect in item["effects"]:
        family = effect["generic"]
        if family not in FIELDS:
            continue
        # Native foX.cL uses (int)eVn.So(1), the raw parameter, not level growth.
        count = int(effect["params"][2])
        if not 0 <= count <= len(ELEMENTS):
            raise ValueError("Unsupported native random element count")
        if selection[FIELDS[family]]:
            raise ValueError(
                "Repeated native element selection requires reroll semantics"
            )
        chosen = (SystemRandom() if rng is None else rng).sample(ELEMENTS, count)
        selection[FIELDS[family]] = sum(1 << element for element in chosen)
        found = True
    return selection if found else None


def save(db, uid, selection):
    schema(db)
    values = masks(selection)
    if values is None:
        return
    db.execute(
        "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(?,?,?)",
        (uid, *values),
    )


def hydrate(db, items):
    schema(db)
    if not items:
        return items
    by_uid = {item["uid"]: item for item in items}
    query = (
        "SELECT uid,damage_elements,resistance_elements FROM inventory_item_elements WHERE uid IN ("
        + ",".join("?" for _ in items)
        + ")"
    )
    for row in db.execute(query, tuple(by_uid)):
        item = by_uid[row["uid"]]
        item.update(
            damage_elements=row["damage_elements"],
            resistance_elements=row["resistance_elements"],
        )
        masks(item)
    return items


def copy(db, source_uid, target_uid):
    schema(db)
    row = db.execute(
        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=?",
        (source_uid,),
    ).fetchone()
    if row is not None:
        save(db, target_uid, dict(row))


def bonuses(item, effect):
    family = effect["generic"]
    if (
        family not in FIELDS
        or effect["parameter_count"] != 2
        or effect["effect_criteria"]
        or effect["has_triggers"]
        or effect["target_mask"] != 0
    ):
        return None
    selected = masks(item)
    if selected is None:
        return {}  # Native eWe.c exits before creating any child eWQ.
    mask = item[FIELDS[family]]
    return {
        STATS[family][element]: effect["values"][0]
        for element in ELEMENTS
        if mask & (1 << element)
    }


def proto(item):
    from .wire import proto_field

    values = masks(item)
    if values is None:
        return b""
    return proto_field(450, proto_field(8, values[0]) + proto_field(16, values[1]))


def binary_options(item):
    values = masks(item)
    if values is None:
        return bytes(8)
    # vj.aF: five absent option flags, vo-present, vR masks, two absent flags.
    return bytes(5) + bytes((1, *values, 0, 0))
