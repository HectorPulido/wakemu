"""Durable native personal QUEST quantities, independent of bag capacity."""
import json
import struct
from pathlib import Path


_SOURCE = json.loads(Path(__file__).with_name("native_quest_items.json").read_text())
REFERENCES = frozenset(_SOURCE["personal_references"])
MAXIMUMS = {int(key): value for key, value in _SOURCE["maximum_quantities"].items()}
if REFERENCES != frozenset(_SOURCE["quest_property_references"]) - frozenset(
    _SOURCE["account_quest_property_references"]
):
    raise ValueError("Inconsistent native quest inventory classification")


class QuestCapacity(ValueError):
    """A valid native quest grant exceeds its owned quantity limit."""


def load(db, character_id):
    return [
        dict(row)
        for row in db.execute(
            "SELECT character_id,reference,quantity FROM character_quest_items "
            "WHERE character_id=%s ORDER BY reference",
            (character_id,),
        )
    ]


def _quantities(character):
    result = {}
    for row in character.get("quest_items", ()):
        reference, quantity = row["reference"], row["quantity"]
        if (
            row["character_id"] != character["id"]
            or reference not in REFERENCES
            or reference in result
            or type(quantity) is not int
            or not 1 <= quantity <= 32767
        ):
            raise ValueError("Invalid owned personal quest item")
        result[reference] = quantity
    return result


def section(character):
    """qB/vh: xI QUEST reference/short quantities and empty vF equipment."""
    quantities = _quantities(character)
    return (
        struct.pack(">H", len(quantities))
        + b"".join(
            struct.pack(">ih", reference, quantity)
            for reference, quantity in sorted(quantities.items())
        )
        + b"\x00" * 4
    )


def changes(before, after):
    """13879/cwN events; quantities are absolute, never replayed deltas."""
    if before["id"] != after["id"]:
        raise ValueError("Foreign quest inventory update")
    old, new = _quantities(before), _quantities(after)
    payload = bytearray(struct.pack(">q", after["id"]))
    for reference in sorted(old.keys() - new.keys()):
        payload.extend(struct.pack(">Bi", 1, reference))
    for reference, quantity in sorted(new.items()):
        if old.get(reference) != quantity:
            payload.extend(
                struct.pack(">Bih", 2 if reference in old else 0, reference, quantity)
            )
    return [] if len(payload) == 8 else [(13879, bytes(payload))]


def grant(db, character_id, reference, quantity):
    """Caller owns the character lock and commits the associated reward once."""
    if (
        reference not in REFERENCES
        or type(quantity) is not int
        or not 1 <= quantity <= 32767
    ):
        raise ValueError("Invalid native personal quest grant")
    before = {"id": character_id, "quest_items": load(db, character_id)}
    if _quantities(before).get(reference, 0) + quantity > MAXIMUMS[reference]:
        raise QuestCapacity("Native personal quest quantity capacity exceeded")
    row = db.execute(
        "INSERT INTO character_quest_items(character_id,reference,quantity) VALUES(%s,%s,%s) "
        "ON CONFLICT(character_id,reference) DO UPDATE SET "
        "quantity=character_quest_items.quantity+EXCLUDED.quantity "
        "RETURNING character_id,reference,quantity",
        (character_id, reference, quantity),
    ).fetchone()
    item = dict(row, quest_item=True)
    after = {"id": character_id, "quest_items": load(db, character_id)}
    item["quest_packet"] = changes(before, after)[0]
    return item


def quantity(character, references):
    counts = {} if character is None else _quantities(character)
    result = 0
    for reference in references:
        if type(reference) is not int or not -(2**63) <= reference < 2**63:
            raise ValueError("Native item reference requires signed long")
        narrowed = ((reference + 2**31) % 2**32) - 2**31
        result = ((result + counts.get(narrowed, 0) + 2**31) % 2**32) - 2**31
    return result
