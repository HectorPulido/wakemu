"""Bounded native import staging; raw bytes and record-key policy stay exact."""
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import sqlite3
import struct
import tempfile

CHUNK_BYTES = 1024 * 1024


@contextmanager
def verified_snapshot(path, checksum, size):
    """Use one immutable disk snapshot for raw storage and derived records."""
    with tempfile.TemporaryFile(mode="w+b") as target:
        digest, actual = hashlib.sha256(), 0
        with Path(path).open("rb") as source:
            for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
                digest.update(chunk)
                actual += len(chunk)
                target.write(chunk)
        if actual != size or digest.hexdigest() != checksum:
            raise ValueError("Native source changed during import: " + str(path))
        target.seek(0)
        yield target


def copy_raw_document(db, revision, path, source, checksum, size):
    """Stream the single bytea field with PostgreSQL's binary COPY protocol."""
    source.seek(0)
    with db.cursor().copy(
        "COPY native_catalog_documents(revision,path,raw,sha256,source_bytes,record_count) "
        "FROM STDIN (FORMAT BINARY)"
    ) as copy:
        copy.write(b"PGCOPY\n\xff\r\n\0" + struct.pack(">ii", 0, 0))
        copy.write(struct.pack(">h", 6))
        for value in (revision.encode("utf8"), path.encode("utf8")):
            copy.write(struct.pack(">i", len(value)))
            copy.write(value)
        copy.write(struct.pack(">i", size))
        actual = 0
        for chunk in iter(lambda: source.read(CHUNK_BYTES), b""):
            copy.write(chunk)
            actual += len(chunk)
        if actual != size:
            raise ValueError("Native snapshot size changed during COPY")
        checksum = checksum.encode("ascii")
        copy.write(struct.pack(">i", len(checksum)))
        copy.write(checksum)
        copy.write(struct.pack(">iq", 8, size))
        copy.write(struct.pack(">ii", 4, 0))
        copy.write(struct.pack(">h", -1))
    source.seek(0)


def _number_values(value):
    # Match json.loads: arbitrary-width integer values and Python float values.
    # ijson's Decimal mode avoids the C backend's use_float/int64 restriction.
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, list):
        return [_number_values(item) for item in value]
    if isinstance(value, dict):
        return {key: _number_values(item) for key, item in value.items()}
    return value


def _value(first, events, *, build):
    from ijson.common import ObjectBuilder

    builder = ObjectBuilder() if build else None
    event, value = first
    depth = int(event in ("start_map", "start_array"))
    if builder is not None:
        builder.event(event, value)
    while depth:
        event, value = next(events)
        if builder is not None:
            builder.event(event, value)
        depth += (event in ("start_map", "start_array")) - (
            event in ("end_map", "end_array")
        )
    return None if builder is None else _number_values(builder.value)


def streamed_records(
    source,
    path,
    *,
    entity_key,
    spatial_directories,
    spatial_collections,
    stage=None,
    index_records=True,
):
    """Index at most one entity at a time with disk-backed duplicate handling.

    SQLite is a disposable spool, never game authority. It preserves Python
    object last-key-wins/first-position order and the existing list suffix rule,
    including literal keys that already resemble generated duplicate suffixes.
    """
    import ijson

    source.seek(0)
    # json.loads(bytes) accepts a UTF-8 BOM without altering the stored bytes.
    if source.read(3) != b"\xef\xbb\xbf":
        source.seek(0)
    events = iter(ijson.basic_parse(source, use_float=False))
    spatial = not index_records or Path(path).parts[0] in spatial_directories
    with tempfile.TemporaryDirectory(prefix="wakemu-catalog-index-") as directory:
        db = sqlite3.connect(str(Path(directory) / "records.sqlite"))
        try:
            db.executescript(
                """
                PRAGMA journal_mode=OFF;
                PRAGMA synchronous=OFF;
                PRAGMA cache_size=-8192;
                PRAGMA temp_store=FILE;
                CREATE TABLE collections(name TEXT PRIMARY KEY,ordinal INTEGER,kind TEXT);
                CREATE TABLE records(collection TEXT,ordinal INTEGER,key TEXT,is_dict INTEGER,payload TEXT,
                    PRIMARY KEY(collection,ordinal));
                CREATE UNIQUE INDEX object_keys ON records(collection,key) WHERE is_dict=1;
                CREATE INDEX base_keys ON records(collection,key);
                CREATE TABLE emitted(collection TEXT,key TEXT,PRIMARY KEY(collection,key));
            """
            )
            sequence = 0

            def collection(name, first):
                nonlocal sequence
                kind = {"start_map": "map", "start_array": "array"}.get(
                    first[0], "scalar"
                )
                db.execute(
                    "INSERT OR IGNORE INTO collections VALUES(?,?,?)",
                    (name, sequence, kind),
                )
                db.execute("UPDATE collections SET kind=? WHERE name=?", (kind, name))
                db.execute("DELETE FROM records WHERE collection=?", (name,))
                sequence += 1
                if spatial or name in spatial_collections or kind == "scalar":
                    _value(first, events, build=False)
                    return
                ordinal = 0
                while True:
                    event, value = next(events)
                    if event == ("end_map" if kind == "map" else "end_array"):
                        break
                    if kind == "map":
                        if event != "map_key":
                            raise ValueError("Invalid native collection object key")
                        key = value
                        payload = _value(next(events), events, build=True)
                    else:
                        payload = _value((event, value), events, build=True)
                        key = entity_key(payload, ordinal)
                    encoded = json.dumps(payload, separators=(",", ":"))
                    if kind == "map":
                        db.execute(
                            "INSERT INTO records VALUES(?,?,?,?,?) "
                            "ON CONFLICT(collection,key) WHERE is_dict=1 DO UPDATE SET payload=excluded.payload",
                            (name, ordinal, key, 1, encoded),
                        )
                    else:
                        db.execute(
                            "INSERT INTO records VALUES(?,?,?,?,?)",
                            (name, ordinal, key, 0, encoded),
                        )
                    ordinal += 1

            first = next(events)
            if first[0] == "start_map":
                while True:
                    event, value = next(events)
                    if event == "end_map":
                        break
                    if event != "map_key":
                        raise ValueError("Invalid native root object key")
                    collection(value, next(events))
            elif first[0] == "start_array":
                collection("$", first)
            else:
                _value(first, events, build=False)
            try:
                next(events)
            except StopIteration:
                pass
            else:
                raise ValueError("Trailing native JSON data")
            db.execute(
                "CREATE TABLE key_counts AS SELECT collection,key,count(*) AS count "
                "FROM records WHERE is_dict=0 GROUP BY collection,key"
            )
            db.execute("CREATE UNIQUE INDEX counted_keys ON key_counts(collection,key)")
            db.commit()
            if stage is not None:
                stage("indexed_spool")
            for name, kind in db.execute(
                "SELECT name,kind FROM collections ORDER BY ordinal"
            ):
                if kind == "map":
                    rows = db.execute(
                        "SELECT key,payload FROM records WHERE collection=? ORDER BY ordinal",
                        (name,),
                    )
                    for key, payload in rows:
                        yield name, key, json.loads(payload)
                elif kind == "array":
                    rows = db.execute(
                        "SELECT r.ordinal,r.key,r.payload,c.count FROM records r "
                        "JOIN key_counts c ON c.collection=r.collection AND c.key=r.key "
                        "WHERE r.collection=? ORDER BY r.ordinal",
                        (name,),
                    )
                    for ordinal, key, payload, count in rows:
                        if count > 1:
                            key = f"{key}@{ordinal}"
                            while (
                                db.execute(
                                    "SELECT 1 FROM key_counts WHERE collection=? AND key=?",
                                    (name, key),
                                ).fetchone()
                                or db.execute(
                                    "SELECT 1 FROM emitted WHERE collection=? AND key=?",
                                    (name, key),
                                ).fetchone()
                            ):
                                key = f"{key}@{ordinal}"
                            db.execute("INSERT INTO emitted VALUES(?,?)", (name, key))
                        yield name, key, json.loads(payload)
        finally:
            db.close()
