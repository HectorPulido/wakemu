"""Native build equipment validation against persisted owned items.

No generic item effects are applied here. Native additional occupations reserve slots; each item is serialized once.
Unsupported EQUIP predicates are rejected before saving a build.
"""
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT
import json
from pathlib import Path
from wakfu_server.wire import proto_fields

RULES = {
    entry["reference"]: entry
    for entry in protocol_catalog.load(DATA_ROOT / "item-equipment-rules.json")["items"]
}


def physical_sheet(character, blob, *, criterion_context=None, ignore_ineligible=False):
    """Validate native ownership, positions and levels before effect evaluation."""
    if type(ignore_ineligible) is not bool:
        raise ValueError("Invalid native equipment eligibility mode")
    if ignore_ineligible and (
        not isinstance(criterion_context, dict)
        or criterion_context.get("actor_kind") != "native_companion_npc"
        or type(criterion_context.get("level")) is not int
        or not 0 <= criterion_context["level"] <= 32767
    ):
        raise ValueError(
            "Ignoring equipment eligibility requires explicit companion context"
        )
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
        level_ineligible = rule["minimum_level"] > character.get(
            "effective_level", character["level"]
        )
        if level_ineligible and not ignore_ineligible:
            raise ValueError(
                "Character level does not meet native equipment requirement"
            )
        occupied = {slot, *rule["occupied_slots"]}
        if occupied & slots or uid in used:
            raise ValueError("Duplicate equipment position or owned unit")
        slots.update(occupied)
        used.add(uid)
        result.append(dict(uid=uid, slot=slot, _level_ineligible=level_ineligible))
    return result


def resolve_sheet(
    character,
    blob,
    *,
    criterion_context=None,
    ignore_ineligible=False,
    native_baseline=None,
    build_index=None,
    include_consumable_buffs=False,
    strict=False
):
    """Resolve effective equipment without rejecting later actor-state changes.

    Structural ownership and unknown authorities remain errors. Admission callers
    opt into strict rejection of false actor predicates; already equipped units
    keep their physical UID and sheet when only their effects become ineligible.
    """
    from .equipment_context import for_character

    if type(strict) is not bool:
        raise ValueError("Invalid native equipment admission mode")
    criterion_context = for_character(character, criterion_context)
    result = physical_sheet(
        character,
        blob,
        criterion_context=criterion_context,
        ignore_ineligible=ignore_ineligible,
    )
    owned = {entry["uid"]: entry for entry in character.get("inventory_items", [])}
    from .equipment_conditions import catalog, evaluate

    conditions = catalog()
    if any(
        "GetCharac"
        in (conditions.get(str(owned[row["uid"]]["reference"]), {}).get("EQUIP") or "")
        for row in result
    ):
        from .equipment_eligibility import reconcile

        return reconcile(
            character,
            result,
            criterion_context=criterion_context,
            native_baseline=native_baseline,
            build_index=build_index,
            include_consumable_buffs=include_consumable_buffs,
        )
    eligible = []
    for row in result:
        if row["_level_ineligible"] and ignore_ineligible:
            # Native fnM.e rejects the actor-level gate before evaluating EQUIP.
            # Physical rows remain in `result` so other predicates still see them.
            continue
        item = owned[row["uid"]]
        by_action = conditions.get(str(item["reference"]))
        if by_action is None:
            raise ValueError("Missing native equipment condition catalog")
        criterion = by_action.get("EQUIP")
        criterion_satisfied = not criterion or evaluate(
            criterion,
            item=item,
            selected=result,
            owned=owned,
            criterion_context=criterion_context,
        )
        if not criterion_satisfied and strict and not ignore_ineligible:
            raise ValueError("Native equipment EQUIP criteria are not satisfied")
        if row["_level_ineligible"] or not criterion_satisfied:
            if strict and not ignore_ineligible:
                raise ValueError("Native equipment is ineligible")
            continue
        eligible.append(dict(uid=row["uid"], slot=row["slot"]))
    return dict(entries=eligible, scalar_overrides={})


def validate_sheet(
    character,
    blob,
    *,
    criterion_context=None,
    ignore_ineligible=False,
    native_baseline=None,
    strict=True
):
    """Validate admission by default; read-only callers explicitly use strict=False."""
    return resolve_sheet(
        character,
        blob,
        criterion_context=criterion_context,
        ignore_ineligible=ignore_ineligible,
        native_baseline=native_baseline,
        strict=strict,
    )["entries"]
