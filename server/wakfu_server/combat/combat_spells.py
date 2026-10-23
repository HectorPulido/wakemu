"""Native unmodified spell costs and current-client cast packet encoders."""
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT
import json, struct
from pathlib import Path
from wakfu_server.spells import available_spells

_COSTS = protocol_catalog.load(DATA_ROOT / "spell-costs.json")["spells"]


def base_costs(character, spell_id):
    spell = next(
        (
            s
            for s in available_spells(
                character["breed"], character["level"], character=character
            )
            if s["id"] == spell_id and s["kind"] == "active"
        ),
        None,
    )
    if spell is None:
        raise ValueError("Spell is not owned/unlocked")
    record = _COSTS.get(str(spell_id))
    if record is None:
        from .combat_common_spell_catalog import merge_cost_records

        record = merge_cost_records(_COSTS).get(str(spell_id))
    if record is None:
        raise ValueError("Missing native owned spell costs")
    index = character["level"] - 1
    if index >= len(record["levels"]):
        raise ValueError("Spell level outside native range")
    ap, mp, wp = record["levels"][index]
    return dict(ap=ap, mp=mp, wp=wp, conditional_rules=record["conditional"])


def spell_wire(character, spell_id, *, native_uid=None, native_level=None):
    if native_uid is not None:
        if (
            type(native_uid) is not int
            or not 0 < native_uid < (1 << 63)
            or type(spell_id) is not int
            or not 0 < spell_id < (1 << 31)
            or type(native_level) is not int
            or not 0 <= native_level <= 32767
        ):
            raise ValueError("Invalid native owned spell identity")
        return struct.pack(">qih", native_uid, spell_id, native_level)
    base_costs(character, spell_id)
    return struct.pack(
        ">qih", (character["id"] << 32) | spell_id, spell_id, character["level"]
    )


def cast_animation(
    fight_id,
    action_id,
    character,
    spell_id,
    target,
    *,
    sequence=-1,
    critical=False,
    failed=False,
    extra=0,
    native_uid=None,
    native_level=None
):
    """12588/cwa: action header, actor, yy, extra, flags, target coords."""
    x, y, z = target
    return (
        struct.pack(">iiiq", fight_id, action_id, sequence, character["id"])
        + spell_wire(
            character, spell_id, native_uid=native_uid, native_level=native_level
        )
        + struct.pack(">iB", extra, int(failed))
        + (b"" if failed else struct.pack(">B", int(critical)))
        + struct.pack(">iih", x, y, z)
    )


def cast_notification(
    fight_id,
    action_id,
    character,
    spell_id,
    target,
    *,
    sequence=-1,
    critical=False,
    failed=False,
    extra=None,
    native_uid=None,
    native_level=None
):
    """12678/cwb: hwe is the spell reference used by aVn chat lookup."""
    if extra is None:
        extra = spell_id
    return (
        struct.pack(
            ">iiiqiBB",
            fight_id,
            action_id,
            sequence,
            character["id"],
            extra,
            int(critical),
            int(failed),
        )
        + spell_wire(
            character, spell_id, native_uid=native_uid, native_level=native_level
        )
        + struct.pack(">iih", *target)
    )
