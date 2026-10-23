"""Spell ownership and deck layouts verified against client sy/yC/yy/fzg."""
from wakfu_server import native_catalog as protocol_catalog
from .paths import DATA_ROOT
import json
import struct
from functools import lru_cache
from pathlib import Path
from protocol_codec import Reader

_DATA = protocol_catalog.load(DATA_ROOT / "spells.json")
SPELLS = {r["id"]: r for r in _DATA["spells"]}
_PINNED_SPELLS = SPELLS
# Original aNr 5623: common active, available while carrying scroll 26347.
COMMON_ITEM_SPELLS = {
    5623: {
        "id": 5623,
        "breed": -2,
        "kind": "active",
        "unlock_level": 130,
        "item_reference": 26347,
        "native_inventory": "account_quest",
    }
}
# Client fzc: six initial active slots; remaining slots and passive slots unlock
# at these exact levels. Spell unlock levels come separately from bdata 66.
ACTIVE_SLOT_LEVELS = (0, 0, 0, 0, 0, 0, 10, 20, 30, 40, 60, 80)
PASSIVE_SLOT_LEVELS = (10, 30, 50, 100, 150, 200)


@lru_cache(maxsize=64)
def _breed_spell_records(breed):
    """Keep ordered references into the process-pinned immutable catalog."""
    return tuple(
        r
        for r in _PINNED_SPELLS.values()
        if r["breed"] == breed or (r["breed"] == -2 and r["kind"] == "passive")
    )


def available_spells(breed, level, *, character=None):
    if type(breed) is not int or type(level) is not int or level < 1:
        raise ValueError("Invalid spell owner breed or level")
    if SPELLS is _PINNED_SPELLS:
        result = [r for r in _breed_spell_records(breed) if r["unlock_level"] <= level]
        return result + item_spells(character, level)
    # Explicit replacement catalogs must never reuse the pinned catalog index.
    return [
        r
        for r in SPELLS.values()
        if (r["breed"] == breed or (r["breed"] == -2 and r["kind"] == "passive"))
        and r["unlock_level"] <= level
    ] + item_spells(character, level)


def item_spells(character, level):
    """Evaluate the native common-spell ownership predicate, never consume it."""
    if character is None:
        return []
    owned = {
        item.get("reference")
        for item in character.get("account_quest_items", ())
        if item.get("quantity", 0) >= 1
        and item.get("account_id") == character.get("account_id")
        and type(item.get("account_id")) is int
    }
    return [
        spell
        for spell in COMMON_ITEM_SPELLS.values()
        if spell["unlock_level"] <= level and spell["item_reference"] in owned
    ]


def owned_spell_records(character):
    """Complete native sy spellbook records shared by encoding and combat."""
    return tuple(
        ((character["id"] << 32) | spell["id"], spell["id"], character["level"])
        for spell in available_spells(
            character["breed"], character["level"], character=character
        )
    )


def spell_inventory(character):
    """sy section: u16 count; (i64 UID,i32 reference,i16 level); two bools."""
    records = owned_spell_records(character)
    return (
        struct.pack(">H", len(records))
        + b"".join(struct.pack(">qih", *record) for record in records)
        + b"\x00\x00"
    )


def common_spell_packet(character):
    """Original ctG12503: owner, then ref/owned UID/level without a count."""
    references = {row["id"] for row in item_spells(character, character["level"])}
    records = [
        record for record in owned_spell_records(character) if record[1] in references
    ]
    if not records:
        raise ValueError("No owned item-enabled common spell")
    return 12503, struct.pack(">q", character["id"]) + b"".join(
        struct.pack(">iqh", reference, uid, level) for uid, reference, level in records
    )


def reconcile_item_spell_decks(character):
    """Hide lost item spells in projected sheets without deleting saved choices."""
    available = {spell["id"] for spell in item_spells(character, character["level"])}
    missing = set(COMMON_ITEM_SPELLS) - available
    result = dict(character)
    builds = dict(character.get("builds", {}))
    for index, build in builds.items():
        blob = bytes.fromhex(build.get("deck", ""))
        if not blob:
            continue
        reader = Reader(blob)
        count = reader.number("i")
        if not 0 <= count <= 12:
            raise ValueError("Invalid saved active deck count")
        active = [reader.number("i") for _ in range(count)]
        count = reader.number("i")
        if not 0 <= count <= 6:
            raise ValueError("Invalid saved passive deck count")
        passive = [reader.number("i") for _ in range(count)]
        cap = reader.number("i")
        reader.finish()
        unavailable = missing | {
            reference
            for reference, spell in COMMON_ITEM_SPELLS.items()
            if cap > 0 and cap < spell["unlock_level"]
        }
        if any(reference in unavailable for reference in active):
            builds[index] = dict(
                build,
                deck=encode_deck(
                    [
                        0 if reference in unavailable else reference
                        for reference in active
                    ],
                    passive,
                    cap,
                ).hex(),
            )
    result["builds"] = builds
    return result


def encode_deck(active=(), passive=(), level_cap=-1):
    """Single fzf, as emitted by fzg.m (last int is a level cap)."""
    if len(active) > 12 or len(passive) > 6:
        raise ValueError("Too many spell deck slots")
    return (
        struct.pack(">i", len(active))
        + b"".join(struct.pack(">i", i) for i in active)
        + struct.pack(">i", len(passive))
        + b"".join(struct.pack(">i", i) for i in passive)
        + struct.pack(">i", level_cap)
    )


def default_deck(character):
    level = character.get("effective_level", character["level"])
    spells = available_spells(character["breed"], level)
    active = [s["id"] for s in spells if s["kind"] == "active"][:6]
    return encode_deck(active, (), -1)


def _validate_deck(blob, breed, level, *, character=None):
    """Check exact fzg.m bytes, ownership, unlock levels and slot capacities."""
    r = Reader(blob)
    result = {}
    for key, max_count in [("active", 12), ("passive", 6)]:
        count = r.number("i")
        if not 0 <= count <= max_count:
            raise ValueError("Invalid spell deck slot count")
        result[key] = [r.number("i") for _ in range(count)]
    result["level_cap"] = r.number("i")
    r.finish()
    cap = result["level_cap"]
    if cap < -1 or cap > level:
        raise ValueError("Invalid spell deck level cap")
    effective_level = cap if cap > 0 else level
    owned = {
        s["id"]: s
        for s in available_spells(breed, effective_level, character=character)
    }
    seen = set()
    for key, thresholds in [
        ("active", ACTIVE_SLOT_LEVELS),
        ("passive", PASSIVE_SLOT_LEVELS),
    ]:
        for index, spell_id in enumerate(result[key]):
            if spell_id == 0:
                continue
            if spell_id in seen:
                raise ValueError("Duplicate spell in deck")
            seen.add(spell_id)
            spell = owned.get(spell_id)
            if spell is None or spell["kind"] != key:
                raise ValueError(
                    "Spell is unavailable for this breed, level or slot type"
                )
            if effective_level < thresholds[index]:
                raise ValueError("Spell slot is locked at this level")
    return result


@lru_cache(maxsize=512)
def _validated_deck(blob, breed, level, catalog_identity):
    """Cache immutable validation results for the process-pinned spell catalog."""
    result = _validate_deck(blob, breed, level)
    return tuple(result["active"]), tuple(result["passive"]), result["level_cap"]


def validate_deck(blob, breed, level, *, character=None):
    """Reuse static validation; return fresh lists for each transaction owner."""
    if character is not None and item_spells(character, level):
        return _validate_deck(blob, breed, level, character=character)
    if (
        not isinstance(blob, (bytes, bytearray, memoryview))
        or (blob.nbytes if isinstance(blob, memoryview) else len(blob)) > 84
        or isinstance(blob, memoryview)
        and (blob.ndim != 1 or blob.itemsize != 1)
        or type(breed) is not int
        or type(level) is not int
    ):
        return _validate_deck(blob, breed, level)
    active, passive, cap = _validated_deck(bytes(blob), breed, level, id(SPELLS))
    return {"active": list(active), "passive": list(passive), "level_cap": cap}
