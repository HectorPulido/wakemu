"""Native PB/eHN signed-byte property counters, shared by retained effects.

Presence is count != 0; removal deletes a count <= 0 after byte subtraction.
This module deliberately does not implement eWt's timeline/collision effects.
"""


def _byte(value):
    return ((value + 128) % 256) - 128


def _validate(counts, property_id):
    if type(property_id) is not int or not -128 <= property_id <= 127:
        raise ValueError("Native PE.aKg signed-byte property required")
    if not isinstance(counts, dict) or any(
        type(k) is not int
        or not -128 <= k <= 127
        or type(v) is not int
        or not -128 <= v <= 127
        for k, v in counts.items()
    ):
        raise ValueError("Complete native PB property counters required")


def add_property(counts, property_id):
    _validate(counts, property_id)
    value = _byte(counts[property_id] + 1) if property_id in counts else 1
    counts[property_id] = value
    return value


def remove_property(counts, property_id):
    _validate(counts, property_id)
    if property_id not in counts:
        return 0
    value = _byte(counts[property_id] - 1)
    if value <= 0:
        del counts[property_id]
        return 0
    counts[property_id] = value
    return value


def property_present(counts, property_id):
    _validate(counts, property_id)
    return counts.get(property_id, 0) != 0
