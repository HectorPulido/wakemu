"""Database-only authority for unchanged original protocol bootstrap records.

Runtime load never opens a capture file. Explicit offline tooling parses the
original source and calls import_records under a caller-owned transaction.
"""
import base64
import binascii
import hashlib
import json
import re
from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

DEFAULT_KEY = "native-bootstrap-v1"


def _key(value):
    if type(value) is not str or not re.fullmatch(
        r"[a-z0-9][a-z0-9._:-]{0,127}", value
    ):
        raise ValueError("Invalid bootstrap capture key")
    return value


def _sha(value):
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Invalid bootstrap capture SHA256")
    return value


def _transaction(db):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Bootstrap authority requires an active transaction")


def canonical_frame(frame):
    """Keep every original field; validate only the native dispatch prerequisites."""
    if type(frame) is not dict or any(type(key) is not str for key in frame):
        raise ValueError("Bootstrap frame must be an object with string keys")
    if frame.get("direction") not in ("in", "out"):
        raise ValueError("Invalid bootstrap frame direction")
    if type(frame.get("opcode")) is not int or not 0 <= frame["opcode"] <= 65535:
        raise ValueError("Invalid bootstrap frame opcode")
    if type(frame.get("body_base64")) is not str:
        raise ValueError("Invalid bootstrap frame body")
    try:
        base64.b64decode(frame["body_base64"], validate=True)
        encoded = json.dumps(
            frame,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, binascii.Error) as exc:
        raise ValueError("Invalid bootstrap frame representation") from exc
    return encoded


def describe(records):
    if type(records) is not list or not 45 <= len(records) <= 1_000_000:
        raise ValueError(
            "Bootstrap capture requires its complete original ordered records"
        )
    digest = hashlib.sha256()
    hashes = []
    for frame in records:
        encoded = canonical_frame(frame)
        hashes.append(hashlib.sha256(encoded).hexdigest())
        digest.update(encoded + b"\n")
    # Main uses this fixed original character-creation anchor unchanged.
    if records[44]["direction"] != "out" or records[44]["opcode"] != 23664:
        raise ValueError("Bootstrap capture is missing its original character anchor")
    return digest.hexdigest(), hashes


def import_records(db, capture_key, source_sha256, records):
    """One-time atomic import; exact replay is read-only, replacements reject."""
    _transaction(db)
    _key(capture_key)
    _sha(source_sha256)
    content_sha, hashes = describe(records)
    # Serialize competing importers even before the manifest row exists.
    db.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        ("bootstrap_capture:" + capture_key,),
    )
    existing = db.execute(
        "SELECT * FROM bootstrap_capture_manifests WHERE capture_key=%s", (capture_key,)
    ).fetchone()
    if existing is not None:
        if (
            existing["source_sha256"],
            existing["content_sha256"],
            existing["frame_count"],
        ) != (source_sha256, content_sha, len(records)):
            raise ValueError(
                "Bootstrap capture key already owns different source records"
            )
        if load(db, capture_key, expected_source_sha256=source_sha256) != records:
            raise ValueError("Bootstrap capture replay differs from stored records")
        return False
    db.execute(
        "INSERT INTO bootstrap_capture_manifests "
        "(capture_key,source_sha256,content_sha256,frame_count) VALUES (%s,%s,%s,%s)",
        (capture_key, source_sha256, content_sha, len(records)),
    )
    with db.cursor() as cursor:
        cursor.executemany(
            "INSERT INTO bootstrap_capture_records "
            "(capture_key,ordinal,payload,payload_sha256) VALUES (%s,%s,%s,%s)",
            [
                (capture_key, index, Jsonb(frame), hashes[index])
                for index, frame in enumerate(records)
            ],
        )
    # Read back the exact DB representation before permitting caller commit.
    if load(db, capture_key, expected_source_sha256=source_sha256) != records:
        raise ValueError("Imported bootstrap records failed database round trip")
    return True


def load(db, capture_key=DEFAULT_KEY, *, expected_source_sha256=None):
    """Read-only, fail-closed runtime bootstrap; no path, parser or file fallback."""
    _transaction(db)
    _key(capture_key)
    if expected_source_sha256 is not None:
        _sha(expected_source_sha256)
    manifest = db.execute(
        "SELECT * FROM bootstrap_capture_manifests WHERE capture_key=%s", (capture_key,)
    ).fetchone()
    if manifest is None:
        raise ValueError("Bootstrap capture is not imported into PostgreSQL")
    _sha(manifest["source_sha256"])
    _sha(manifest["content_sha256"])
    if (
        expected_source_sha256 is not None
        and manifest["source_sha256"] != expected_source_sha256
    ):
        raise ValueError("Bootstrap source SHA256 differs from expected authority")
    rows = db.execute(
        "SELECT ordinal,payload,payload_sha256 FROM bootstrap_capture_records "
        "WHERE capture_key=%s ORDER BY ordinal",
        (capture_key,),
    ).fetchall()
    if type(manifest["frame_count"]) is not int or len(rows) != manifest["frame_count"]:
        raise ValueError("Bootstrap capture record count differs from manifest")
    records = []
    for index, row in enumerate(rows):
        if row["ordinal"] != index:
            raise ValueError("Bootstrap capture ordinal sequence is incomplete")
        encoded = canonical_frame(row["payload"])
        if hashlib.sha256(encoded).hexdigest() != row["payload_sha256"]:
            raise ValueError("Bootstrap capture record SHA256 mismatch")
        records.append(row["payload"])
    content_sha, _ = describe(records)
    if content_sha != manifest["content_sha256"]:
        raise ValueError("Bootstrap capture ordered content SHA256 mismatch")
    return records
