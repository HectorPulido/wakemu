"""Explicit DB-scoped native LootChest definition reconstruction.

The original fg/bEH field1 reader refreshes bCI.dSG; field2 hydrates its state.
Original assets, UID, position and reward ownership remain independent.
"""

import hashlib
import json

# Trust anchors identify the installed binary source, not a gameplay policy.
DEFINITION_SOURCE_SHA256 = (
    "a95e2f1c0c3c9bd7ccfb59c42f329f7547235ef156826bb76d727b781f2f0ec8"
)
PROTOTYPE_CONTENT_SHA256 = (
    "1393910d0e5e1f59f65f4df750f118544007dca7cb820574575eef1f3acc5caa"
)


def _prototypes(db):
    rows = [
        dict(r)
        for r in db.execute(
            "SELECT * FROM native_loot_chest_prototypes ORDER BY p"
        ).fetchall()
    ]
    digest = hashlib.sha256(
        json.dumps(rows, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    if digest != PROTOTYPE_CONTENT_SHA256:
        raise ValueError("Original LootChest prototype source changed")
    return {row["p"]: row for row in rows}


def binding(db, rule):
    row = db.execute(
        "SELECT * FROM declared_treasure_definition_overrides WHERE map_id=%s AND object_id=%s",
        (rule["map_id"], rule["object_id"]),
    ).fetchone()
    if row is None:
        return None
    row = dict(row)
    prototype = _prototypes(db).get(row["replacement_definition"])
    if (
        row["sealed"] is not True
        or rule["native_family"] != "LootChest"
        or row["original_definition"] != rule["descriptor_id"]
        or row["catalog_revision"] != rule["catalog_revision"]
        or row["original_definition_missing"] is not True
        or row["definition_source_sha256"] != DEFINITION_SOURCE_SHA256
        or prototype is None
        or row["native_action"] != 22
        or row["native_mru"] != prototype["egY"]
        or (
            row["required_item"],
            row["required_quantity"],
            row["required_kamas"],
            row["criterion"],
        )
        != (prototype["emb"], prototype["emc"], prototype["ema"], prototype["ehu"])
        or row["replacement_definition"] <= 0
        or row["required_item"] != 0
        or row["required_quantity"] != 0
        or row["required_kamas"] != 0
        or row["criterion"] != "not IsHero()"
        or not row["authority"]
        or len(row["definition_source_sha256"]) != 64
    ):
        raise ValueError("Unqualified treasure definition reconstruction")
    return row


def project_snapshot_rows(store, map_id, rows):
    """Project existing same-UID rows before their FIRST native13984 hydration.

    Called on the original scene's already-filtered neighborhood. Fields0/1
    come from the attested asset; field2 is the caller's actual native state.
    No extra object or delayed second registration is introduced.
    """
    rows = [dict(row) for row in rows]
    if not rows:
        return rows
    ids = {row["id"] for row in rows}
    with store.connection() as db:
        sources = db.execute(
            "SELECT l.* FROM declared_treasure_locations l "
            "JOIN declared_treasure_definition_overrides o USING(map_id,object_id) "
            "WHERE l.map_id=%s AND l.object_id=ANY(%s)",
            (map_id, list(ids)),
        ).fetchall()
        bindings = {r["object_id"]: (dict(r), binding(db, dict(r))) for r in sources}
    if not bindings:
        return rows
    from wakfu_server.declared_treasure_rewards import _source
    from wakfu_server.native_interactive_components import rebind_definition
    from wakfu_server import native_catalog

    for row in rows:
        found = bindings.get(row["id"])
        if found is None:
            continue
        rule, override = found
        if override is None or native_catalog.release() != rule["catalog_revision"]:
            raise ValueError("Missing active treasure projection authority")
        _source(
            rule["catalog_revision"],
            map_id,
            rule["object_id"],
            rule["native_family"],
            rule["payload_hex"],
            rule["state_payload_hex"],
            rule["geometry_sha256"],
            rule["x"],
            rule["y"],
            rule["z"],
        )
        row["payload_hex"] = rebind_definition(
            bytes.fromhex(rule["payload_hex"]),
            bytes.fromhex(row["payload_hex"]),
            expected_parameter=str(override["original_definition"]),
            replacement_parameter=str(override["replacement_definition"]),
        ).hex()
    return rows


def project_snapshot_bodies(store, map_id, bodies):
    """Project original cwJ13984 batches without importing the world catalog.

    This retains the original count/UID/i16-length grammar and batch ordering.
    The World caller uses it before its first native scene registration.
    """
    import struct

    result = []
    for body in bodies:
        if type(body) is not bytes or len(body) < 2:
            raise ValueError("Truncated native interactive snapshot batch")
        count = struct.unpack_from(">h", body)[0]
        if count < 0:
            raise ValueError("Invalid native interactive snapshot count")
        cursor = 2
        rows = []
        for _ in range(count):
            if cursor + 10 > len(body):
                raise ValueError("Truncated native interactive snapshot row")
            identity, length = struct.unpack_from(">qh", body, cursor)
            cursor += 10
            if length < 0 or cursor + length > len(body):
                raise ValueError("Invalid native interactive snapshot payload length")
            rows.append(
                dict(id=identity, payload_hex=body[cursor : cursor + length].hex())
            )
            cursor += length
        if cursor != len(body):
            raise ValueError("Trailing native interactive snapshot bytes")
        projected = project_snapshot_rows(store, map_id, rows)
        encoded = bytearray(struct.pack(">h", len(projected)))
        for row in projected:
            payload = bytes.fromhex(row["payload_hex"])
            if len(payload) > 32767:
                raise ValueError(
                    "Native interactive projection exceeds payload grammar"
                )
            encoded.extend(struct.pack(">qh", row["id"], len(payload)))
            encoded.extend(payload)
        result.append(bytes(encoded))
    return tuple(result)
