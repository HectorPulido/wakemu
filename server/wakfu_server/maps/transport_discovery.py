"""Account-scoped known ZAAP/DRAGO IDs, using native fzy/zR wire schema.

Discovery is distinct from routing: a known ID does not authorize a destination.
"""
from .paths import DATA_ROOT
import struct


def _varint(value):
    out = bytearray()
    while value > 127:
        out.append((value & 127) | 128)
        value >>= 7
    out.append(value)
    return bytes(out)


def _validate(kind, identity):
    if (
        type(kind) is not int
        or kind not in (1, 2)
        or type(identity) is not int
        or not 0 < identity < 2**31
    ):
        raise ValueError("Invalid native transport discovery")


def discovery_packet(kind, identity):
    _validate(kind, identity)
    return 12674, struct.pack(">iB", identity, kind)


def account_packet(known):
    """13873 section12; eDX/fzy consumes i32 protobuf length then zR."""
    proto = bytearray()
    for kind in (2, 1):  # Same order as fzy.foH; semantic sets do not depend on order.
        values = sorted(set(known.get(kind, ())))
        body = bytearray((8, kind))
        for identity in values:
            _validate(kind, identity)
            body.extend(b"\x10" + _varint(identity))
        proto.extend(b"\x0a" + _varint(len(body)) + body)
    return 13873, struct.pack(">iii", 1, 12, len(proto)) + proto


class Discoveries:
    def __init__(self, store):
        self.store = store
        with store.connection() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS transport_discoveries(
                account_id INTEGER NOT NULL,kind INTEGER NOT NULL CHECK(kind IN(1,2)),
                transport_id INTEGER NOT NULL, PRIMARY KEY(account_id,kind,transport_id))"""
            )

    def known(self, account_id):
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT kind,transport_id FROM transport_discoveries WHERE account_id=?",
                (account_id,),
            ).fetchall()
            return {
                kind: tuple(row["transport_id"] for row in rows if row["kind"] == kind)
                for kind in (1, 2)
            }

    def discover(self, account_id, generation, kind, identity):
        _validate(kind, identity)
        with self.store.connection() as db:
            db.execute("BEGIN IMMEDIATE")
            session = db.execute(
                "SELECT 1 FROM sessions WHERE account_id=? AND generation=? AND expires_at>?",
                (account_id, generation, self.store.clock()),
            ).fetchone()
            if session is None:
                raise ValueError("Transport discovery session is stale")
            return (
                db.execute(
                    "INSERT OR IGNORE INTO transport_discoveries VALUES(?,?,?)",
                    (account_id, kind, identity),
                ).rowcount
                == 1
            )


def known_all(*, include_dragos=False):
    """Explicit local test policy; native IDs only, independent of saved discovery."""
    import json
    from pathlib import Path

    catalog = json.loads((DATA_ROOT / "native-transports.json").read_text())
    objects = json.loads((DATA_ROOT / "native-transport-objects.json").read_text())
    routable = {
        row["id"] for row in objects if len(row.get("arrival_heights", ())) == 1
    }
    return {
        kind: tuple(
            sorted(
                row["id"]
                for row in catalog
                if row["kind"] == kind and row["id"] in routable
            )
        )
        for kind in ((1, 2) if include_dragos else (1,))
    }


def local_policy(known, *, all_zaaps=False, all_dragos=False):
    """Project explicit local availability without overwriting saved discoveries.

    Send account_packet(result) to the client AND use result for backend routing.
    Client known-set gating occurs before it sends travel13686.
    """
    result = {kind: tuple(sorted(set(known.get(kind, ())))) for kind in (1, 2)}
    if all_zaaps or all_dragos:
        available = known_all(include_dragos=all_dragos)
        for kind, enabled in ((1, all_zaaps), (2, all_dragos)):
            if enabled:
                result[kind] = available[kind]
    return result
