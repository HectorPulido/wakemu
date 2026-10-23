"""Transaction-scoped achievement persistence; reward delivery is external.

The caller owns commit/rollback and account/session authorization. Character
row locks serialize all changes, including events and outbox reservations.
"""
import hashlib
import json

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

from wakfu_server.maps.dungeon_achievement_authority import queries_from_snapshot


def _lock(db, character_id):
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Achievement storage requires an active transaction")
    if type(character_id) is not int or character_id <= 0:
        raise ValueError("Invalid achievement character")
    row = db.execute(
        "SELECT id FROM characters WHERE id=%s FOR UPDATE", (character_id,)
    ).fetchone()
    if row is None:
        raise ValueError("Missing achievement character")


def _json(value):
    if not isinstance(value, dict):
        raise ValueError("Achievement payload must be an object")

    # Stable signatures reject non-finite floats and non-string mapping keys.
    def validate(node):
        if isinstance(node, dict):
            if any(not isinstance(key, str) for key in node):
                raise ValueError("Achievement JSON keys must be strings")
            for child in node.values():
                validate(child)
        elif isinstance(node, list):
            for child in node:
                validate(child)

    validate(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _key(value):
    if not isinstance(value, str) or not 1 <= len(value) <= 256:
        raise ValueError("Invalid achievement persistence key")
    return value


def _state(state):
    if not isinstance(state, dict) or set(state) != {
        "variables",
        "objectives",
        "running",
        "completed",
        "tracking",
        "recent",
        "completion_dates",
    }:
        raise ValueError("Invalid achievement progress state")
    if not isinstance(state["variables"], dict) or any(
        not isinstance(key, str)
        or not key.isascii()
        or not key.isdigit()
        or not 0 < int(key) < 2**31
        or type(value) is not int
        or not 0 <= value < 2**63
        for key, value in state["variables"].items()
    ):
        raise ValueError("Invalid achievement variables")
    if (
        not isinstance(state["tracking"], list)
        or len(state["tracking"]) > 255
        or any(
            type(value) is not int or not 0 < value < 2**31
            for value in state["tracking"]
        )
    ):
        raise ValueError("Invalid tracked achievements")
    if (
        not isinstance(state["recent"], list)
        or len(state["recent"]) > 255
        or any(
            not isinstance(value, dict)
            or set(value) != {"id", "date_ms"}
            or type(value["id"]) is not int
            or not 0 < value["id"] < 2**31
            or type(value["date_ms"]) is not int
            or not 0 <= value["date_ms"] < 2**63
            for value in state["recent"]
        )
    ):
        raise ValueError("Invalid recent achievements")
    if not isinstance(state["completion_dates"], dict) or any(
        not isinstance(key, str)
        or not key.isascii()
        or not key.isdigit()
        or not 0 < int(key) < 2**31
        or type(value) is not int
        or not 0 <= value < 2**63
        for key, value in state["completion_dates"].items()
    ):
        raise ValueError("Invalid achievement completion dates")
    projection = {key: state[key] for key in ("running", "completed", "objectives")}
    queries_from_snapshot(projection)
    if any(value >= 2**31 for values in projection.values() for value in values):
        raise ValueError("Achievement identifiers exceed native signed32")
    _json(state)
    return projection


def load_locked(db, character_id):
    """Load mutable state under the character lock, preserving existing facts."""
    _lock(db, character_id)
    row = db.execute(
        "SELECT state FROM character_achievement_progress WHERE character_id=%s",
        (character_id,),
    ).fetchone()
    if row is not None:
        _state(row["state"])
        return json.loads(_json(row["state"]))
    authority = db.execute(
        "SELECT snapshot FROM character_achievement_authority "
        "WHERE character_id=%s FOR UPDATE",
        (character_id,),
    ).fetchone()
    if authority is None:
        raise ValueError("Missing initialized achievement authority")
    queries_from_snapshot(authority["snapshot"])
    return {
        "variables": {},
        "tracking": [],
        "recent": [],
        "completion_dates": {},
        **json.loads(_json(authority["snapshot"])),
    }


def store(db, character_id, state):
    """Persist progress and access-criterion authority in the same transaction."""
    projection = _state(state)
    _lock(db, character_id)
    authority = db.execute(
        "UPDATE character_achievement_authority SET snapshot=%s, "
        "revision=revision+1, provenance='local_achievement_engine', "
        "updated_at=CURRENT_TIMESTAMP WHERE character_id=%s RETURNING revision",
        (Jsonb(projection), character_id),
    ).fetchone()
    if authority is None:
        raise ValueError("Missing initialized achievement authority")
    return db.execute(
        "INSERT INTO character_achievement_progress(character_id,state) VALUES (%s,%s) "
        "ON CONFLICT(character_id) DO UPDATE SET state=EXCLUDED.state, "
        "revision=character_achievement_progress.revision+1, "
        "updated_at=CURRENT_TIMESTAMP RETURNING revision",
        (character_id, Jsonb(state)),
    ).fetchone()["revision"]


def record_event(db, character_id, event_key, payload):
    """Reserve an event once; a reused identity with different facts is invalid."""
    signature = hashlib.sha256(_json(payload).encode("utf-8")).hexdigest()
    _key(event_key)
    _lock(db, character_id)
    inserted = db.execute(
        "INSERT INTO character_achievement_events "
        "(character_id,event_key,signature,payload) VALUES (%s,%s,%s,%s) "
        "ON CONFLICT(character_id,event_key) DO NOTHING RETURNING event_key",
        (character_id, event_key, signature, Jsonb(payload)),
    ).fetchone()
    if inserted is not None:
        return True
    existing = db.execute(
        "SELECT signature FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character_id, event_key),
    ).fetchone()
    if existing["signature"] != signature:
        raise ValueError("Achievement event identity conflicts with stored facts")
    return False


def enqueue_reward(db, character_id, achievement_id, cycle_key, reward_key, payload):
    """Reserve a unique reward for a transaction-scoped delivery hook."""
    if isinstance(payload, dict) and payload.get("aeV") == 17:
        from .scaled_xp import reserve

        # A missing policy or invalid native parameter must not leave an
        # unpriced entitlement behind when the caller handles the exception.
        with db.transaction():
            inserted = _enqueue_reward(
                db, character_id, achievement_id, cycle_key, reward_key, payload
            )
            reserve(db, character_id, achievement_id, cycle_key, reward_key, payload)
        return inserted
    return _enqueue_reward(
        db, character_id, achievement_id, cycle_key, reward_key, payload
    )


def _enqueue_reward(db, character_id, achievement_id, cycle_key, reward_key, payload):
    if type(achievement_id) is not int or not 0 < achievement_id < 2**31:
        raise ValueError("Invalid achievement reward owner")
    _key(cycle_key)
    _key(reward_key)
    canonical = _json(payload)
    _lock(db, character_id)
    inserted = db.execute(
        "INSERT INTO character_achievement_reward_outbox "
        "(character_id,achievement_id,cycle_key,reward_key,payload) "
        "VALUES (%s,%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING reward_key",
        (character_id, achievement_id, cycle_key, reward_key, Jsonb(payload)),
    ).fetchone()
    if inserted is not None:
        return True
    existing = db.execute(
        "SELECT payload FROM character_achievement_reward_outbox "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s",
        (character_id, achievement_id, cycle_key, reward_key),
    ).fetchone()
    if _json(existing["payload"]) != canonical:
        raise ValueError("Achievement reward identity conflicts with stored facts")
    return False


def claim_reward(db, character_id, achievement_id, cycle_key, reward_id, payload):
    """Reserve before granting; caller must grant and mark within this transaction."""
    return enqueue_reward(
        db, character_id, achievement_id, cycle_key, str(reward_id), payload
    )


def mark_reward_delivered(db, character_id, achievement_id, cycle_key, reward_id):
    """Mark only after the actual grant succeeds in the same transaction."""
    _lock(db, character_id)
    row = db.execute(
        "UPDATE character_achievement_reward_outbox "
        "SET delivered_at=COALESCE(delivered_at,CURRENT_TIMESTAMP) "
        "WHERE character_id=%s AND achievement_id=%s AND cycle_key=%s AND reward_key=%s "
        "RETURNING reward_key",
        (character_id, achievement_id, cycle_key, str(reward_id)),
    ).fetchone()
    if row is None:
        raise ValueError("Missing achievement reward reservation")


def enqueue_notifications(db, character_id, event_key, packets):
    """Persist already serialized server packet envelopes, without publishing."""
    _key(event_key)
    if not isinstance(packets, list) or any(
        not isinstance(packet, dict)
        or set(packet) != {"opcode", "payload_hex"}
        or type(packet["opcode"]) is not int
        or not 0 <= packet["opcode"] < 2**16
        or not isinstance(packet["payload_hex"], str)
        for packet in packets
    ):
        raise ValueError("Invalid achievement notification packets")
    for packet in packets:
        try:
            bytes.fromhex(packet["payload_hex"])
        except ValueError as error:
            raise ValueError("Invalid achievement notification payload") from error
    canonical = _json({"packets": packets})
    _lock(db, character_id)
    row = db.execute(
        "INSERT INTO character_achievement_notifications(character_id,event_key,packets) "
        "VALUES (%s,%s,%s) ON CONFLICT DO NOTHING RETURNING event_key",
        (character_id, event_key, Jsonb(packets)),
    ).fetchone()
    if row is not None:
        return True
    previous = db.execute(
        "SELECT packets FROM character_achievement_notifications "
        "WHERE character_id=%s AND event_key=%s",
        (character_id, event_key),
    ).fetchone()
    if _json({"packets": previous["packets"]}) != canonical:
        raise ValueError(
            "Achievement notification identity conflicts with stored facts"
        )
    return False


def pending_notifications(db, character_id):
    """Read pending batches under the caller's transaction; publication is at-least-once."""
    _lock(db, character_id)
    return [
        dict(row)
        for row in db.execute(
            "SELECT event_key,packets FROM character_achievement_notifications "
            "WHERE character_id=%s AND delivered_at IS NULL ORDER BY created_at,event_key",
            (character_id,),
        ).fetchall()
    ]


def mark_notifications_delivered(db, character_id, event_key):
    _key(event_key)
    _lock(db, character_id)
    row = db.execute(
        "UPDATE character_achievement_notifications "
        "SET delivered_at=COALESCE(delivered_at,CURRENT_TIMESTAMP) "
        "WHERE character_id=%s AND event_key=%s RETURNING event_key",
        (character_id, event_key),
    ).fetchone()
    if row is None:
        raise ValueError("Missing achievement notification reservation")


def pending_rewards(db, character_id):
    """Lock undelivered reservations for atomic grant and delivery marking."""
    _lock(db, character_id)
    return [
        dict(row)
        for row in db.execute(
            "SELECT achievement_id,cycle_key,reward_key,payload,delivered_at "
            "FROM character_achievement_reward_outbox "
            "WHERE character_id=%s AND delivered_at IS NULL "
            "ORDER BY created_at,achievement_id,cycle_key,reward_key FOR UPDATE",
            (character_id,),
        ).fetchall()
    ]
