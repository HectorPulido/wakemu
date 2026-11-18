"""Read-only lookup for native order-trial mission settlement receipts."""

from __future__ import annotations

import hashlib
import json


def expected_event_key(fight_id):
    """Return the shared-toolkit key derived from the producer's fight token."""
    from wakfu_server.achievements import native_order_trial_settlement

    rule = native_order_trial_settlement.load_rule()
    identity = hashlib.sha256(
        json.dumps(
            dict(
                admission_id=rule.admission_id,
                event_reference=rule.event_reference,
                minimum_score=rule.minimum_score,
                evidence=rule.evidence,
            ),
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    token = f"native-order-trial:{int(fight_id)}:{identity}"
    token_digest = hashlib.sha256(token.encode()).hexdigest()
    return f"mission-toolkit:scenario_completed:{rule.event_reference}:{token_digest}"


def receipt_for_fight(db, character_id, fight_id, *, expected_map_id=None):
    """Fetch the one exact toolkit receipt and verify its persisted event facts."""
    from wakfu_server.achievements import native_order_trial_settlement

    rule = native_order_trial_settlement.load_rule()
    key = expected_event_key(fight_id)
    row = db.execute(
        "SELECT event_key,payload FROM character_achievement_events "
        "WHERE character_id=%s AND event_key=%s",
        (character_id, key),
    ).fetchone()
    if row is None:
        return None
    payload = row["payload"]
    if (
        not isinstance(payload, dict)
        or payload.get("kind") != "scenario_completed"
        or payload.get("reference") != rule.event_reference
        or payload.get("quantity") != 1
        or (expected_map_id is not None and payload.get("map_id") != expected_map_id)
    ):
        raise ValueError("Native order-trial receipt has conflicting persisted facts")
    return row


def settled_trial_fights(store, character_id):
    """Find qualifying accepted trial checkpoints with their exact durable receipt."""
    from wakfu_server.native_order_trial_checkpoint import validate

    with store.connection() as db:
        rows = db.execute(
            "SELECT p.fight_id,c.snapshot FROM combat_fight_participants p "
            "JOIN fight_checkpoints c ON c.fight_id=p.fight_id "
            "WHERE p.character_id=%s ORDER BY p.fight_id",
            (character_id,),
        ).fetchall()
        settled = []
        for row in rows:
            snapshot = row["snapshot"]
            if not isinstance(snapshot, dict) or snapshot.get("phase") != "finished":
                continue
            document = snapshot.get("native_order_trial")
            if document is None:
                continue
            proof, rules, state = validate(document, encounter_id=row["fight_id"])
            if (
                proof.owner_id != character_id
                or not state.hard_mode
                or state.score < rules.score_threshold
            ):
                continue
            admission = document.get("admission")
            source_map_id = (
                admission.get("source_map_id") if isinstance(admission, dict) else None
            )
            receipt = receipt_for_fight(
                db, character_id, row["fight_id"], expected_map_id=source_map_id
            )
            if receipt is not None:
                settled.append(row["fight_id"])
    return settled
