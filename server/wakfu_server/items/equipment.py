"""Native build equipment validation against persisted owned items.

No generic item effects are applied here. Native additional occupations reserve slots; each item is serialized once.
Unsupported EQUIP predicates are rejected before saving a build.
"""
from .paths import DATA_ROOT
import json
from pathlib import Path
from wakfu_server.wire import proto_fields

RULES = {
    entry["reference"]: entry
    for entry in json.loads((DATA_ROOT / "item-equipment-rules.json").read_text())[
        "items"
    ]
}


def validate_sheet(character, blob):
    owned = {entry["uid"]: entry for entry in character.get("inventory_items", [])}
    slots, used = set(), set()
    result = []
    for tag, value in proto_fields(blob):
        if tag == 424:
            level = (value & 0xFFFFFFFF) - (1 << 32) if value & (1 << 31) else value
            if level not in (-1, character["level"]):
                raise ValueError("Invalid equipment sheet level")
            continue
        if tag != 10 or not isinstance(value, bytes):
            raise ValueError("Invalid equipment sheet field")
        fields = list(proto_fields(value))
        values = dict(fields)
        if len(fields) != 2 or len(values) != 2 or set(values) != {8, 16}:
            raise ValueError("Invalid native equipment item")
        uid, slot = values[8], values[16]
        item = owned.get(uid)
        if (
            item is None
            or item["character_id"] != character["id"]
            or item["quantity"] != 1
        ):
            raise ValueError("Equipment references an unavailable or unowned unit")
        rule = RULES.get(item["reference"])
        if rule is None or slot not in rule["slots"]:
            raise ValueError("Item does not support this native equipment slot")
        if rule["minimum_level"] > character.get("effective_level", character["level"]):
            raise ValueError(
                "Character level does not meet native equipment requirement"
            )
        occupied = {slot, *rule["occupied_slots"]}
        if occupied & slots or uid in used:
            raise ValueError("Duplicate equipment position or owned unit")
        slots.update(occupied)
        used.add(uid)
        result.append(dict(uid=uid, slot=slot))
    from .equipment_conditions import catalog, evaluate
    conditions = catalog()
    for row in result:
        item = owned[row["uid"]]
        by_action = conditions.get(str(item["reference"]))
        if by_action is None:
            raise ValueError("Missing native equipment condition catalog")
        criterion = by_action.get("EQUIP")
        if criterion and not evaluate(criterion, item=item, selected=result, owned=owned):
            raise ValueError("Native equipment EQUIP criteria are not satisfied")
    return result
