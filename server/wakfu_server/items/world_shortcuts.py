"""Native 12091 deltas and so/sq/yv/yw/yu WORLD shortcut snapshots.

Bar coordinates are type, relative bar number and slot, not global UI indices.
This codec does not grant items or modify combat decks.
"""
import struct

from protocol_codec import Reader

BAR_LIMITS = {0: (4, 8), 1: (4, 6), 2: (1, 8)}
MAX_POSITIONS = sum(bars * slots for bars, slots in BAR_LIMITS.values())
DESCRIPTOR = struct.Struct(">bqii")


def coordinate(key):
    if type(key) is not int or not 0 <= key <= 0xFFFFFF:
        raise ValueError("Invalid shortcut coordinate")
    kind, bar, slot = key >> 16, (key >> 8) & 255, key & 255
    limits = BAR_LIMITS.get(kind)
    if limits is None or bar >= limits[0] or slot >= limits[1]:
        raise ValueError("Shortcut coordinate exceeds native bar limits")
    return kind, bar, slot


def decode(body):
    """Read the complete native delta before callers validate or mutate state.

    Removals precede assignments; assigning a removed coordinate replaces it.
    Duplicate removals are harmless. Duplicate assignments are ambiguous.
    Non-WORLD coordinates remain explicit for routing by their domain owner.
    """
    reader = Reader(body)
    actor_id = reader.number("q")
    if actor_id <= 0:
        raise ValueError("Invalid shortcut character identity")
    count = reader.number("h")
    if not 0 <= count <= MAX_POSITIONS * 2:
        raise ValueError("Invalid shortcut removal count")
    removals = set()
    for _ in range(count):
        removals.add(coordinate(reader.number("i")))
    count = reader.number("h")
    if not 0 <= count <= MAX_POSITIONS:
        raise ValueError("Invalid shortcut assignment count")
    assignments = {}
    for _ in range(count):
        position = coordinate(reader.number("i"))
        if position in assignments:
            raise ValueError("Duplicate shortcut assignment")
        kind, identity, reference, extra = DESCRIPTOR.unpack(
            reader.take(DESCRIPTOR.size)
        )
        assignments[position] = dict(
            shortcut_type=kind,
            long_value=identity,
            int_value=reference,
            extra_int=extra,
        )
    reader.finish()
    return dict(actor_id=actor_id, removals=sorted(removals), assignments=assignments)


def collection(entries):
    """Restore four WORLD bars, including empty predecessors, deterministically."""
    bars = [[] for _ in range(BAR_LIMITS[0][0])]
    seen = set()
    for entry in entries:
        bar, slot = entry["bar_number"], entry["slot"]
        if (
            type(bar) is not int
            or type(slot) is not int
            or not 0 <= bar < 4
            or not 0 <= slot < 8
        ):
            raise ValueError("Invalid persisted WORLD shortcut position")
        position = (0, bar, slot)
        if position in seen:
            raise ValueError("Duplicate persisted shortcut position")
        seen.add(position)
        if entry["shortcut_type"] not in (1, 2):
            raise ValueError("Unsupported WORLD item shortcut type")
        bars[bar].append((slot, entry))
    result = struct.pack(">H", len(bars))
    for entries in bars:
        result += struct.pack(">bH", 0, len(entries))
        for slot, entry in sorted(entries, key=lambda pair: pair[0]):
            result += struct.pack(">h", slot) + DESCRIPTOR.pack(
                entry["shortcut_type"],
                entry["long_value"],
                entry["int_value"],
                entry["extra_int"],
            )
    return result


def load(db, character_id):
    return [
        dict(row)
        for row in db.execute(
            "SELECT bar_number,slot,shortcut_type,long_value,int_value,extra_int "
            "FROM character_world_shortcuts WHERE character_id=%s ORDER BY bar_number,slot",
            (character_id,),
        )
    ]


def apply(store, account_id, generation, character_id, body):
    """Persist received WORLD item edits atomically without inventory mutation.

    Reference shortcuts survive exhaustion; UID shortcuts are restored only
    while the same owned entity exists. Other bar domains are not modified.
    """
    request = decode(body)
    if request["actor_id"] != character_id:
        raise ValueError("Shortcut edits belong to another character")
    from .inventory_actions import RULES
    from .inventory_consumables import CATALOG

    usable = {
        ref for ref, rule in RULES.items() if rule["use_action_id"] is not None
    } | set(CATALOG)
    with store.connection() as db:
        store.lock_character(db, account_id, generation, character_id)
        owned = {
            row["uid"]: row["reference"]
            for row in db.execute(
                "SELECT uid,reference FROM inventory_items WHERE character_id=%s",
                (character_id,),
            )
        }
        previous = {
            (0, row["bar_number"], row["slot"]): row for row in load(db, character_id)
        }
        edits = {
            pos: value for pos, value in request["assignments"].items() if pos[0] == 0
        }
        for position, value in edits.items():
            kind, identity, reference = (
                value["shortcut_type"],
                value["long_value"],
                value["int_value"],
            )
            if reference not in usable or kind not in (1, 2):
                raise ValueError("Unsupported WORLD consumable shortcut")
            if kind == 1:
                replay = previous.get(position)
                unchanged = replay is not None and all(
                    replay[key] == value[key] for key in value
                )
                if identity != reference or (
                    reference not in owned.values() and not unchanged
                ):
                    raise ValueError("Unavailable owned reference shortcut")
            elif owned.get(identity) != reference:
                raise ValueError("Unavailable or foreign item shortcut")
        for kind, bar, slot in request["removals"]:
            if kind == 0:
                db.execute(
                    "DELETE FROM character_world_shortcuts WHERE character_id=%s AND bar_number=%s AND slot=%s",
                    (character_id, bar, slot),
                )
        for (_, bar, slot), value in edits.items():
            db.execute(
                "INSERT INTO character_world_shortcuts VALUES(%s,%s,%s,%s,%s,%s,%s) "
                "ON CONFLICT(character_id,bar_number,slot) DO UPDATE SET "
                "shortcut_type=excluded.shortcut_type,long_value=excluded.long_value,"
                "int_value=excluded.int_value,extra_int=excluded.extra_int",
                (
                    character_id,
                    bar,
                    slot,
                    value["shortcut_type"],
                    value["long_value"],
                    value["int_value"],
                    value["extra_int"],
                ),
            )
        return store.character(account_id, character_id, db)


def owned_collection(character):
    owned = {
        item["uid"]: item["reference"] for item in character.get("inventory_items", ())
    }
    return collection(
        [
            entry
            for entry in character.get("world_shortcuts", ())
            if entry["shortcut_type"] == 1
            or owned.get(entry["long_value"]) == entry["int_value"]
        ]
    )
