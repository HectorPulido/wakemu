"""Pinned original aMR definitions; learned sources are not construction models."""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path


SOURCE_SHA256 = "733982c0f8b5ac033756f4f2377aac766f1e6beba4a6620096cadf2b93a25c4b"


@lru_cache(maxsize=1)
def definitions():
    raw = (
        Path(__file__).with_name("native_ranch_building_definitions.json").read_bytes()
    )
    if sha256(raw).hexdigest() != SOURCE_SHA256:
        raise ValueError("Native Ranch building catalog differs from its source")
    document = json.loads(raw)
    if document.get("schema_version") != 1 or document.get("native_class") != "aMR":
        raise ValueError("Unsupported native Ranch building catalog")
    result = {row["p"]: row for row in document["definitions"]}
    if len(result) != len(document["definitions"]):
        raise ValueError("Duplicate native Ranch building definition")
    return result


def definition(reference):
    if type(reference) is not int or reference not in definitions():
        raise ValueError(
            "This learned plan has no installed native building definition"
        )
    return definitions()[reference]


def mode(building, mode_id=None):
    identity = building["epF"] if mode_id is None else mode_id
    result = next((row for row in building["epD"] if row["p"] == identity), None)
    if result is None:
        raise ValueError("Native Ranch building mode is unavailable")
    return result


def view(building, mode_id, kind, value):
    selected = mode(building, mode_id)
    if kind == 0:
        result = next(
            (row["epM"] for row in selected["epP"] if row["epS"] == value), None
        )
    elif kind == 1:
        result = next(
            (row["epM"] for row in selected["epQ"] if row["epL"] == value), None
        )
    else:
        result = None
    if result is None:
        raise ValueError("Native Ranch building view is unavailable for this mode")
    return result


def validate_published(db, reference):
    expected = definition(reference)
    row = db.execute(
        "SELECT descriptor,source_sha256 FROM native_ranch_building_definitions WHERE reference=%s",
        (reference,),
    ).fetchone()
    if (
        row is None
        or row["source_sha256"] != SOURCE_SHA256
        or row["descriptor"] != expected
    ):
        raise ValueError("Published native Ranch building definition has changed")
    return expected
