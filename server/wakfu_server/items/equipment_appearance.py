"""Owned active equipment projected into native pO and csP slot maps."""
import struct


def rows(character):
    """Resolve actual owned units; skin zero selects the native item reference."""
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.builds import valid_index, effective_sheet_level

    index = character.get("active_build_index", 0)
    if not valid_index(index):
        raise ValueError("Invalid active appearance equipment sheet")
    level = effective_sheet_level(character, index)
    saved = character.get("builds", {}).get(index, {})
    selected = validate_sheet(
        dict(character, level=level, effective_level=level),
        bytes.fromhex(saved.get("equipment", "")),
    )
    units = {item["uid"]: item for item in character.get("inventory_items", [])}
    # Owned units currently have no persisted item-skin override authority.
    return tuple(
        sorted(
            (entry["slot"], units[entry["uid"]]["reference"], 0) for entry in selected
        )
    )


def section(character):
    """Native pO: unsigned count followed by slot/reference/skin pR entries."""
    selected = rows(character)
    if len(selected) > 127:
        raise ValueError("Equipment appearance exceeds native update count")
    return bytes((len(selected),)) + b"".join(
        struct.pack(">Bii", *entry) for entry in selected
    )


def change_packet(previous, current):
    """Native csP updates changed slots, explicitly removing unequipped slots."""
    if any(previous[key] != current[key] for key in ("id", "account_id")):
        raise ValueError("Equipment appearance publication belongs to another actor")
    before = {
        slot: (reference, skin or reference) for slot, reference, skin in rows(previous)
    }
    after = {
        slot: (reference, skin or reference) for slot, reference, skin in rows(current)
    }
    changed = [
        (slot, *after.get(slot, (0, 0)))
        for slot in sorted(before.keys() | after.keys())
        if before.get(slot) != after.get(slot)
    ]
    if not changed:
        return None
    if len(changed) > 127:
        raise ValueError("Equipment appearance exceeds native update count")
    body = struct.pack(">qB", current["id"], len(changed))
    return 13060, body + b"".join(struct.pack(">Bii", *entry) for entry in changed)
