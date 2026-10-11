"""Explicit local rarity allocation; native rollMax is retained, not interpreted.

Caps count successful bundles, not item quantities. The caller owns the award
transaction. Serializing on the durable fight row makes fight-wide scope atomic
across recipients; immutable receipts make retries independent of fresh RNG.
"""
from dataclasses import asdict, replace
from decimal import Decimal
from hashlib import sha256
import json

from psycopg.pq import TransactionStatus
from psycopg.types.json import Jsonb

POLICY = "wakemu-local-rarity-allocation-v1"
SETTING = "combat_drop_allocation_policy"
_DECIMALS = ("base_probability", "raw_probability", "effective_probability")


def validate_policy(policy):
    if not isinstance(policy, dict) or policy.get("policy") != POLICY:
        raise ValueError("Invalid local drop allocation policy")
    if policy.get("scope") not in ("recipient_item", "fight_item"):
        raise ValueError("Invalid local drop allocation scope")
    if type(policy.get("enabled", True)) is not bool:
        raise ValueError("Invalid local allocation enabled flag")
    caps = policy.get("rarity_caps")
    if not isinstance(caps, dict) or not caps:
        raise ValueError("Missing native rarity caps")
    for key, cap in caps.items():
        if not isinstance(key, str) or not key.isdecimal():
            raise ValueError("Invalid native rarity code")
        if cap is not None and (type(cap) is not int or not 0 <= cap <= 1000000):
            raise ValueError("Invalid successful bundle cap")
    return json.loads(json.dumps(policy))


def filter_decisions(decisions, *, policy, rarities, consumed=None):
    """Allocate in existing plan order; never change probability or quantity draws."""
    policy = validate_policy(policy)
    counts = dict(consumed or {})
    output, audit = [], []
    for decision in decisions:
        if not decision.success:
            output.append(decision)
            continue
        reference = decision.item_reference
        rarity = rarities.get(reference)
        if type(rarity) is not int or str(rarity) not in policy["rarity_caps"]:
            raise ValueError(
                "Successful drop has no authoritative native rarity policy"
            )
        cap = policy["rarity_caps"][str(rarity)]
        before = counts.get(reference, 0)
        allowed = cap is None or before < cap
        audit.append(
            {
                "item_reference": reference,
                "rarity_code": rarity,
                "cap": cap,
                "consumed_before": before,
                "allowed": allowed,
                "planned_success": decision.success,
                "planned_quantity": decision.quantity,
                "planned_quantity_draw_numerator": decision.quantity_draw_numerator,
                "defeated_actor_id": decision.defeated_actor_id,
                "drop_row_index": decision.drop_row_index,
                "attempt_index": decision.attempt_index,
            }
        )
        if allowed:
            counts[reference] = before + 1
            output.append(decision)
        else:
            output.append(
                replace(
                    decision, success=False, quantity=None, quantity_draw_numerator=None
                )
            )
    return tuple(output), audit, counts


def _encode(decision):
    row = asdict(decision)
    for name in _DECIMALS:
        row[name] = str(row[name])
    return row


def _decode(row):
    from .combat_drops import DropDecision

    row = dict(row)
    for name in _DECIMALS:
        row[name] = Decimal(row[name])
    return DropDecision(**row)


def allocate(db, fight_id, character_id, decisions):
    """Return durable filtered decisions and snapshot in the caller transaction.

    Existing receipt replay ignores newly supplied decisions and does not read
    the current policy or native mappings. Award persistence must share this
    transaction, so failure rolls back both allocation and the award.
    """
    if db.info.transaction_status != TransactionStatus.INTRANS:
        raise ValueError("Drop allocation requires an active transaction")
    if (
        type(fight_id) is not int
        or fight_id <= 0
        or type(character_id) is not int
        or character_id <= 0
    ):
        raise ValueError("Invalid drop allocation identity")
    installed = db.execute(
        "SELECT to_regclass('fight_drop_allocations') AS installed"
    ).fetchone()
    if installed is None or installed["installed"] is None:
        return tuple(decisions), {
            "policy": POLICY,
            "enabled": False,
            "reason": "migration_absent",
        }
    if (
        db.execute(
            "SELECT id FROM combat_fights WHERE id=%s FOR UPDATE", (fight_id,)
        ).fetchone()
        is None
    ):
        raise ValueError("Unknown allocation fight")
    if (
        db.execute(
            "SELECT character_id FROM combat_fight_participants WHERE fight_id=%s AND character_id=%s",
            (fight_id, character_id),
        ).fetchone()
        is None
    ):
        raise ValueError("Unknown allocation recipient")
    old = db.execute(
        "SELECT snapshot FROM fight_drop_allocations WHERE fight_id=%s AND character_id=%s",
        (fight_id, character_id),
    ).fetchone()
    if old is not None:
        snapshot = old["snapshot"]
        return tuple(_decode(row) for row in snapshot["decisions"]), snapshot
    pinned = db.execute(
        "SELECT policy FROM fight_drop_allocation_policies WHERE fight_id=%s",
        (fight_id,),
    ).fetchone()
    if pinned is None:
        setting = db.execute(
            "SELECT value FROM settings WHERE name=%s FOR SHARE", (SETTING,)
        ).fetchone()
        if setting is None:
            raise ValueError("Missing local allocation policy")
        policy = validate_policy(setting["value"])
        db.execute(
            "INSERT INTO fight_drop_allocation_policies(fight_id,policy) VALUES(%s,%s)",
            (fight_id, Jsonb(policy)),
        )
    else:
        policy = validate_policy(pinned["policy"])
    if not policy.get("enabled", True):
        filtered, audit, after, counts, rows = tuple(decisions), [], {}, {}, []
    else:
        return _allocate_enabled(db, fight_id, character_id, decisions, policy)
    return _persist(
        db, fight_id, character_id, filtered, policy, audit, after, counts, rows
    )


def _allocate_enabled(db, fight_id, character_id, decisions, policy):
    references = sorted({d.item_reference for d in decisions if d.success})
    rows = db.execute(
        "SELECT reference,rarity_code,source_sha256 FROM native_drop_item_rarities WHERE reference=ANY(%s)",
        (references,),
    ).fetchall()
    rarities = {row["reference"]: row["rarity_code"] for row in rows}
    counts = {}
    if policy["scope"] == "fight_item":
        for row in db.execute(
            "SELECT snapshot FROM fight_drop_allocations WHERE fight_id=%s ORDER BY character_id",
            (fight_id,),
        ):
            for key, count in row["snapshot"]["accepted_counts"].items():
                reference = int(key)
                counts[reference] = counts.get(reference, 0) + count
    filtered, audit, after = filter_decisions(
        decisions, policy=policy, rarities=rarities, consumed=counts
    )
    return _persist(
        db, fight_id, character_id, filtered, policy, audit, after, counts, rows
    )


def _persist(db, fight_id, character_id, filtered, policy, audit, after, counts, rows):
    accepted = {
        str(key): value - counts.get(key, 0)
        for key, value in after.items()
        if value > counts.get(key, 0)
    }
    snapshot = {
        "policy": policy,
        "fight_id": fight_id,
        "character_id": character_id,
        "native_rarity_sources": sorted({row["source_sha256"] for row in rows}),
        "accepted_counts": accepted,
        "allocations": audit,
        "decisions": [_encode(d) for d in filtered],
    }
    digest = sha256(
        json.dumps(snapshot, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    db.execute(
        "INSERT INTO fight_drop_allocations(fight_id,character_id,snapshot,snapshot_sha256) VALUES(%s,%s,%s,%s)",
        (fight_id, character_id, Jsonb(snapshot), digest),
    )
    return filtered, snapshot
