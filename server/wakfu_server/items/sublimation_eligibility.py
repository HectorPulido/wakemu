"""Installed fpR target predicates and independent native attachment slots."""
import json

CLIENT_JAR_SHA256 = "e3eb8b9b6a1fa0d42d2f06f0af3e841ed783b2998f5c81d3cd8312294106d3cd"
SPECIAL_RARITIES = {"EPIC": 7, "RELIC": 5}


def pattern(db, reference):
    row = db.execute(
        "SELECT slot_colors,pattern_type,client_jar_sha256 "
        "FROM native_sublimation_patterns WHERE reference=%s AND enabled=TRUE",
        (reference,),
    ).fetchone()
    if row is None:
        raise ValueError("Sublimation reference has no enabled native pattern")
    return decode_pattern(row)


def decode_pattern(row):
    """Validate the same native authority for SQL mutations and fight snapshots."""
    colors = row["slot_colors"]
    if isinstance(colors, str):
        colors = json.loads(colors)
    kind = row["pattern_type"]
    if (
        row["client_jar_sha256"] != CLIENT_JAR_SHA256
        or kind not in {"BASIC", "EPIC", "RELIC"}
        or not isinstance(colors, (list, tuple))
        or any(type(color) is not int or color not in range(5) for color in colors)
        or (kind == "BASIC" and not 1 <= len(colors) <= 4)
        or (kind != "BASIC" and len(colors) != 0)
    ):
        raise ValueError("Malformed native sublimation pattern")
    return dict(kind=kind, colors=tuple(colors), tag=24 if kind == "BASIC" else 32)


def special_target(db, reference, *, kind=None):
    row = db.execute(
        "SELECT item_level,pattern_type,rarity_code,client_jar_sha256 "
        "FROM native_sublimation_targets WHERE reference=%s AND enabled=TRUE",
        (reference,),
    ).fetchone()
    if row is None:
        raise ValueError(
            "Target rarity does not accept this native special sublimation"
        )
    return decode_special_target(row, kind=kind)


def decode_special_target(row, *, kind=None):
    """Validate an exported target without reading mutable inventory state."""
    if (
        row["client_jar_sha256"] != CLIENT_JAR_SHA256
        or row["pattern_type"] not in SPECIAL_RARITIES
        or type(row["rarity_code"]) is not int
        or row["rarity_code"] != SPECIAL_RARITIES[row["pattern_type"]]
        or type(row["item_level"]) is not int
        or row["item_level"] < 0
    ):
        raise ValueError("Malformed native sublimation target authority")
    if kind is not None and row["pattern_type"] != kind:
        raise ValueError(
            "Target rarity does not accept this native special sublimation"
        )
    return row
