"""eMm equipment type ancestry, over the actual selected owned equipment.

Numeric operands narrow to Java short; any matching type ancestor succeeds.
The native inventory flag additionally includes bag contents. Slot-name overloads
remain unsupported until the fnO slot-name contract is supplied.
"""
from functools import lru_cache


@lru_cache(maxsize=1)
def type_catalog():
    from wakfu_server import native_catalog
    from wakfu_server.paths import DATA_ROOT

    return native_catalog.load(DATA_ROOT / "native-equipment-type-index.json")


def matches_types(references, requested, catalog):
    wanted = {((int(value) + 32768) % 65536) - 32768 for value in requested}
    for reference in references:
        kind = catalog["items"].get(str(reference))
        if kind is None:
            raise ValueError("Missing native equipment item type")
        seen = set()
        while kind:
            if kind in wanted:
                return True
            if kind in seen or str(kind) not in catalog["types"]:
                raise ValueError("Invalid native equipment type ancestry")
            seen.add(kind)
            kind = catalog["types"][str(kind)]
    return False


def character_has_equipment_type(character, requested, include_inventory=False):
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.builds import effective_sheet_level, valid_index

    index = character.get("active_build_index", 0)
    if not valid_index(index):
        raise ValueError("Invalid active equipment sheet")
    adjusted = dict(character, level=effective_sheet_level(character, index))
    sheet = character.get("builds", {}).get(index, {})
    selected = validate_sheet(adjusted, bytes.fromhex(sheet.get("equipment", "")))
    owned = {row["uid"]: row for row in character.get("inventory_items", [])}
    references = [owned[row["uid"]]["reference"] for row in selected]
    if include_inventory:
        references.extend(row["reference"] for row in owned.values())
    if not references:
        return False
    return matches_types(references, requested, type_catalog())
