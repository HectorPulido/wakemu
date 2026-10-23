"""Persisted fnR.foX element choices, never assigned before identification.

New selectable items carry zero masks until the native 12487 choice. The
client treats these masks as unidentified; existing saved choices remain intact.
"""

ELEMENTS = (1, 2, 3, 4)
FIELDS = {1068: "damage_elements", 1069: "resistance_elements"}
STATS = {1068: {1: 21, 2: 22, 3: 23, 4: 24}, 1069: {1: 28, 2: 29, 3: 30, 4: 31}}
VALID_MASK = sum(1 << element for element in ELEMENTS)


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


def create(reference):
    from .equipment_stats import CATALOG

    item = CATALOG.get(reference)
    if item is None:
        return None
    selection = dict(damage_elements=0, resistance_elements=0)
    seen = set()
    for effect in item["effects"]:
        family = effect["generic"]
        if family not in FIELDS:
            continue
        # Native selectable element count is the raw parameter, not level growth.
        count = int(effect["params"][2])
        if not 0 <= count <= len(ELEMENTS):
            raise ValueError("Unsupported native selectable element count")
        if family in seen:
            raise ValueError(
                "Repeated native element selection requires reroll semantics"
            )
        seen.add(family)
    return selection if seen else None


def save(db, uid, selection):
    values = masks(selection)
    if values is None:
        return
    db.execute(
        "INSERT INTO inventory_item_elements(uid,damage_elements,resistance_elements) VALUES(%s,%s,%s)",
        (uid, *values),
    )


def hydrate(db, items):
    if not items:
        return items
    by_uid = {item["uid"]: item for item in items}
    for row in db.execute(
        "SELECT uid,damage_elements,resistance_elements FROM inventory_item_elements "
        "WHERE uid = ANY(%s)",
        (list(by_uid),),
    ):
        item = by_uid[row["uid"]]
        item.update(
            damage_elements=row["damage_elements"],
            resistance_elements=row["resistance_elements"],
        )
        masks(item)
    return items


def copy(db, source_uid, target_uid):
    row = db.execute(
        "SELECT damage_elements,resistance_elements FROM inventory_item_elements WHERE uid=%s",
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
    from wakfu_server.wire import proto_field

    values = masks(item)
    if values is None:
        return b""
    return proto_field(450, proto_field(8, values[0]) + proto_field(16, values[1]))


def binary_options(item):
    values = masks(item)
    from .inventory_shards import option as shard_option

    sockets = shard_option(item)
    # vj.aF option order: vv, vE, vA, vm, vk, vo, vs, vu. vA's payload is
    # the native yp representation; vo carries the two elemental masks.
    from .pet_codec import binary_option as pet_option

    state = item.get("pet", item.get("mount"))
    result = bytearray(pet_option(state))
    result.append(0)
    if sockets is None:
        result.append(0)
    else:
        result.append(1)
        result.extend(sockets)
    from .inventory_companion_info import binary_option as companion_option

    result.extend(companion_option(item))
    from .item_binding import binary_option as binding_option

    result.extend(binding_option(item))
    if values is None:
        result.append(0)
    else:
        result.extend((1, *values))
    from .item_appearance import binary_option

    result.append(0)
    result.extend(binary_option(item))
    return bytes(result)
