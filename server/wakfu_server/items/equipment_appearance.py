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
    from wakfu_server.item_appearance import reference as appearance_reference

    appearances = {
        entry["slot"]: (
            units[entry["uid"]]["reference"],
            appearance_reference(units[entry["uid"]]),
        )
        for entry in selected
    }
    record = character.get("owned_cosmetics")
    if record is not None:
        from wakfu_server.characters.cosmetics import OwnedCosmetics

        owned = OwnedCosmetics.from_record(
            record, account_id=character.get("account_id")
        )
        # Original eSP.r(fnO), including cosmetic-only visuals on empty slots.
        for category, slot in (
            (8, 0),
            (9, 5),
            (10, 3),
            (11, 13),
            (12, 12),
            (13, 15),
            (14, 16),
        ):
            reference = owned.selected_single(character["id"], category)
            if reference:
                base_reference = appearances.get(slot, (0, 0))[0]
                appearances[slot] = (base_reference, reference)
    return tuple((slot, *values) for slot, values in sorted(appearances.items()))


def section(character):
    """Native pO: unsigned count followed by slot/reference/skin pR entries."""
    selected = rows(character)
    if len(selected) > 127:
        raise ValueError("Equipment appearance exceeds native update count")
    return bytes((len(selected),)) + b"".join(
        struct.pack(">Bii", *entry) for entry in selected
    )


def snapshot_packet(character):
    """Publish the selected equipment's visual slots without rebuilding actors."""
    selected = rows(character)
    if len(selected) > 127:
        raise ValueError("Equipment appearance exceeds native update count")
    return 13060, struct.pack(">qB", character["id"], len(selected)) + b"".join(
        struct.pack(">Bii", slot, reference, skin or reference)
        for slot, reference, skin in selected
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
