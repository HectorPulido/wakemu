"""Native fBQ/13754 encoding for complete durable account herd records.

Every instance field is mandatory. This module never constructs a default
creature, consumes a source, infers initial attributes, or mutates account data.
"""
import math
import struct

_FIELDS = frozenset(
    (
        "definition",
        "uid",
        "birth_ms",
        "attributes",
        "name",
        "scale",
        "native_tJT",
        "native_eqf",
        "native_tJU",
        "x",
        "y",
        "z",
        "native_tJR",
        "native_tJV",
    )
)


def _int(value, bits, label):
    if type(value) is not int or not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise ValueError("Invalid ranch " + label)
    return value


def encode_creature(record):
    """Encode a fully specified owned instance, preserving raw native fields."""
    if not isinstance(record, dict) or set(record) != _FIELDS:
        raise ValueError("A complete attested ranch instance is required")
    definition = _int(record["definition"], 32, "definition")
    uid = _int(record["uid"], 64, "UID")
    if definition <= 0 or uid <= 0:
        raise ValueError("Invalid ranch physical identity")
    attributes = record["attributes"]
    if (
        not isinstance(attributes, dict)
        or len(attributes) > 32767
        or not isinstance(record["name"], str)
    ):
        raise ValueError("Invalid ranch instance attributes/name")
    name = record["name"].encode("utf-8")
    if len(name) > 127:
        raise ValueError("Native ranch name exceeds signed byte UTF-8 length")
    scale = record["scale"]
    if type(scale) not in (int, float) or not math.isfinite(scale) or scale <= 0:
        raise ValueError("Invalid ranch instance scale")
    for flag in ("native_tJT", "native_tJV"):
        if type(record[flag]) is not bool:
            raise ValueError("Invalid native ranch Boolean")
    parts = [
        struct.pack(
            ">iqqh",
            definition,
            uid,
            _int(record["birth_ms"], 64, "birth date"),
            len(attributes),
        )
    ]
    # fBQ serializes a map. Deterministic ordering changes no identity/value.
    for key, value in sorted(attributes.items()):
        parts.append(
            struct.pack(
                ">ii",
                _int(key, 32, "attribute identity"),
                _int(value, 32, "attribute amount"),
            )
        )
    parts.append(struct.pack(">B", len(name)) + name)
    parts.append(
        struct.pack(
            ">fBiqiihqB",
            scale,
            record["native_tJT"],
            _int(record["native_eqf"], 32, "eqf"),
            _int(record["native_tJU"], 64, "tJU"),
            _int(record["x"], 32, "x"),
            _int(record["y"], 32, "y"),
            _int(record["z"], 16, "z"),
            _int(record["native_tJR"], 64, "tJR"),
            record["native_tJV"],
        )
    )
    return b"".join(parts)


def creature_delta(records, *, added):
    """Native czS13754 uses complete instances for both add and removal."""
    if type(added) is not bool or not isinstance(records, (tuple, list)):
        raise ValueError("Invalid ranch delta")
    _int(len(records), 32, "delta count")
    encoded = [encode_creature(record) for record in records]
    if len({record["uid"] for record in records}) != len(records):
        raise ValueError("Duplicate owned UID in ranch delta")
    return 13754, struct.pack(">Bi", added, len(encoded)) + b"".join(encoded)


def component18(records, *, biomes_payload, known_buildings, new_buildings):
    """Compose owned creatures with actual biome and building authorities.

    The second native animal collection fCi is not implemented. Callers with
    that collection must not use this bounded codec. Actual biome bytes are a
    required argument rather than an invented empty-state replacement.
    """
    if not isinstance(biomes_payload, bytes):
        raise ValueError("Actual biome serialization is required")
    _, delta = creature_delta(records, added=True)
    creatures = delta[1:] + struct.pack(">i", 0)

    def references(values):
        if not isinstance(values, (tuple, list)) or len(set(values)) != len(values):
            raise ValueError("Invalid ranch building collection")
        for ref in values:
            if _int(ref, 32, "building reference") <= 0:
                raise ValueError("Invalid ranch building reference")
        return struct.pack(">i", len(values)) + b"".join(
            struct.pack(">i", ref) for ref in sorted(values)
        )

    buildings = references(known_buildings) + references(new_buildings)
    return b"".join(
        struct.pack(">i", len(part)) + part
        for part in (creatures, biomes_payload, buildings)
    )


def encode_paddock(record):
    """Native fBS: physical UID, group, signed-short interior/boundary points."""
    if not isinstance(record, dict):
        raise ValueError("Invalid native Ranch enclosure")
    uid = _int(record["uid"], 64, "paddock UID")
    if uid <= 0:
        raise ValueError("Invalid native Ranch paddock identity")
    parts = [struct.pack(">qi", uid, _int(record["group"], 32, "paddock group"))]
    for key in ("interior", "boundary"):
        points = record[key]
        if not isinstance(points, (tuple, list)) or len(points) > 8000:
            raise ValueError("Native Ranch enclosure point limit exceeded")
        if any(
            not isinstance(point, (tuple, list)) or len(point) != 2 for point in points
        ):
            raise ValueError("Invalid native Ranch enclosure point")
        if len({tuple(point) for point in points}) != len(points):
            raise ValueError("Duplicate native Ranch enclosure point")
        parts.append(struct.pack(">h", len(points)))
        for x, y in sorted(points):
            parts.append(
                struct.pack(">ii", _int(x, 32, "paddock X"), _int(y, 32, "paddock Y"))
            )
    return b"".join(parts)


def account_animals(records):
    """Full fxS owned fBQ collection plus the empty unimplemented fCi domain."""
    return creature_delta(records, added=True)[1][1:] + struct.pack(">i", 0)
