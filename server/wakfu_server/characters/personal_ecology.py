"""Absolute personal ecology and idempotent, transaction-owned updates.

Callers authorize the character lease and resolve population/policy before
calling apply in the same transaction as the ecological action.
"""
import struct
from psycopg.types.json import Jsonb
from .ecology_progression import basis_points, native_score, LIMIT


def value(number):
    return basis_points(number)


def packet(character_id, absolute):
    if type(character_id) is not int or not 0 < character_id < 2**63:
        raise ValueError("Invalid ecology character")
    return 13574, struct.pack(">qi", character_id, native_score(absolute))


def snapshot(character):
    """Own and observer join state; never reconstruct it from a percent."""
    return (packet(character["id"], character.get("ecology_value", 0)),)


def apply(db, character_id, *, operation, delta, evidence, national_action=False):
    packet(character_id, 0)
    value(delta)
    if not isinstance(operation, str) or not 1 <= len(operation) <= 128:
        raise ValueError("Invalid ecology operation")
    if type(evidence) is not dict:
        raise ValueError("Invalid ecological evidence")
    if type(national_action) is not bool:
        raise ValueError("Invalid live national ecology action")
    actor = db.execute(
        "SELECT ecology_value,ecology_revision FROM characters WHERE id=%s FOR UPDATE",
        (character_id,),
    ).fetchone()
    if actor is None:
        raise ValueError("Unknown ecology character")
    prior = db.execute(
        "SELECT * FROM personal_ecology_receipts WHERE character_id=%s AND operation=%s",
        (character_id, operation),
    ).fetchone()
    if prior is not None:
        if prior["requested_delta"] != delta or prior["evidence"] != evidence:
            raise ValueError("Ecology operation reused with different evidence")
        # Replaying an old action must not roll the client gauge backwards.
        return {
            "duplicate": True,
            "receipt": dict(prior),
            "packet": packet(character_id, actor["ecology_value"]),
        }
    before = value(actor["ecology_value"])
    after = max(-LIMIT, min(LIMIT, before + delta))
    revision = actor["ecology_revision"] + 1
    receipt = db.execute(
        "INSERT INTO personal_ecology_receipts(character_id,operation,requested_delta,"
        "before_value,after_value,revision,evidence) VALUES(%s,%s,%s,%s,%s,%s,%s) RETURNING *",
        (character_id, operation, delta, before, after, revision, Jsonb(evidence)),
    ).fetchone()
    db.execute(
        "UPDATE characters SET ecology_value=%s,ecology_revision=%s WHERE id=%s",
        (after, revision, character_id),
    )
    if national_action:
        from .national_earnings import ecology

        ecology(db, character_id, operation)
    return {
        "duplicate": False,
        "receipt": dict(receipt),
        "packet": packet(character_id, after),
    }
