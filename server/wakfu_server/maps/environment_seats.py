"""Leased occupancy for installed stools and original native occupation packets."""
import struct
import hashlib

from wakfu_server.inventory_items import _lease
from wakfu_server.environment_interactions import _guard
from wakfu_server import world_static


def request(body):
    if len(body) != 12:
        raise ValueError("Invalid stool request")
    identity, action, parameter = struct.unpack(">qHH", body)
    if identity <= 0 or action not in (6, 7) or parameter:
        raise ValueError("Unsupported stool action")
    return identity, action


def occupancy(identity, actor_id):
    payload = bytes.fromhex("01030000000603") + struct.pack(">q", actor_id)
    return 12344, struct.pack(">qH", identity, len(payload)) + payload


def stop(actor_id):
    return 12088, struct.pack(">Bhqi", 3, 16, actor_id, 0)


def _prune(store, db):
    db.execute(
        "DELETE FROM environment_seats e WHERE NOT EXISTS "
        "(SELECT 1 FROM sessions s WHERE s.account_id=e.account_id "
        "AND s.generation=e.generation AND s.character_id=e.character_id AND s.expires_at>%s)",
        (store.now(),),
    )


def sit(
    store,
    account_id,
    generation,
    character,
    body,
    *,
    in_range,
    animation_verified=False,
    blocked=False
):
    """Claim a seat after the caller verifies native approach geometry.

    The explicit range authority avoids inventing a distance rule. Returned owner
    packets and scene packets must be delivered separately by the world session.
    """
    identity, action = request(body)
    if action == 7:
        return release(
            store, account_id, generation, character["id"], object_id=identity
        )
    if (
        type(in_range) is not bool
        or not in_range
        or blocked
        or character.get("instance_id", 0)
    ):
        raise ValueError("Stool is unavailable at the current position")
    rule = next(
        (
            r
            for r in world_static.objects(character["map_id"])
            if r["id"] == identity and r["type"] == "Stool"
        ),
        None,
    )
    if rule is None:
        raise ValueError("Unsupported installed stool")
    if type(animation_verified) is not bool or not animation_verified:
        raise ValueError("Stool animation support is not verified for this actor")
    with store.connection() as db:
        _lease(store, db, account_id, generation, character["id"])
        _guard(db, character["id"])
        definition = db.execute(
            "SELECT payload_sha256 FROM environment_seat_definitions "
            "WHERE map_id=%s AND object_id=%s",
            (character["map_id"], identity),
        ).fetchone()
        if (
            definition is None
            or definition["payload_sha256"]
            != hashlib.sha256(bytes.fromhex(rule["payload_hex"])).hexdigest()
        ):
            raise ValueError("Stool requires unsupported native eligibility criteria")
        # Serialize competing claims without locking unrelated seat identities.
        db.execute(
            "SELECT pg_advisory_xact_lock(%s,%s)", (character["map_id"], identity)
        )
        _prune(store, db)
        current = db.execute(
            "SELECT * FROM environment_seats WHERE character_id=%s", (character["id"],)
        ).fetchone()
        if current is not None:
            if (
                current["map_id"] == character["map_id"]
                and current["object_id"] == identity
            ):
                return dict(current, replay=True, packets=[], scene_packets=[])
            raise ValueError("Actor already occupies another stool")
        occupied = db.execute(
            "SELECT 1 FROM environment_seats WHERE map_id=%s AND object_id=%s",
            (character["map_id"], identity),
        ).fetchone()
        if occupied:
            raise ValueError("Stool is occupied")
        row = db.execute(
            "INSERT INTO environment_seats VALUES(%s,%s,%s,%s,%s) RETURNING *",
            (character["map_id"], identity, account_id, generation, character["id"]),
        ).fetchone()
    return dict(
        row,
        replay=False,
        packets=[(13579, struct.pack(">Bhqq", 1, 16, identity, character["id"]))],
        scene_packets=[occupancy(identity, character["id"])],
    )


def release(store, account_id, generation, character_id, *, object_id=None):
    """Idempotently release only this connection's occupancy, including logout."""
    with store.connection() as db:
        row = db.execute(
            "SELECT * FROM environment_seats WHERE account_id=%s AND generation=%s "
            "AND character_id=%s FOR UPDATE",
            (account_id, generation, character_id),
        ).fetchone()
        if row is None:
            return {"packets": [], "scene_packets": []}
        if object_id is not None and row["object_id"] != object_id:
            raise ValueError("Actor does not occupy the requested stool")
        db.execute(
            "DELETE FROM environment_seats WHERE character_id=%s", (character_id,)
        )
    return dict(
        row,
        packets=[stop(character_id)],
        scene_packets=[occupancy(row["object_id"], 0)],
    )


def snapshots(store, map_id):
    with store.connection() as db:
        _prune(store, db)
        rows = db.execute(
            "SELECT object_id,character_id FROM environment_seats WHERE map_id=%s",
            (map_id,),
        ).fetchall()
    occupied = {r["object_id"]: r["character_id"] for r in rows}
    # Include free stools so lease expiry clears an observer's prior overlay.
    return [
        occupancy(r["id"], occupied.get(r["id"], 0))
        for r in world_static.objects(map_id)
        if r["type"] == "Stool"
    ]
