"""Semantic identities for durable simulation decisions and latest state.

Random outcomes belong to a durable cycle, not to each planner pass. State
snapshots instead coalesce while pending and keep distinct delivery IDs when
their authoritative version changes, so late acknowledgements remain safe.
"""
import hashlib

from .protocol import json_bytes


def _digest(value):
    return hashlib.sha256(json_bytes(value)).hexdigest()


def identity(row):
    """Return (pending slot, version, durable decision ID or None)."""
    payload = row["payload"]
    domain = row["domain"]
    kind = payload.get("kind", payload.get("operation"))
    base = [row["world_epoch"], domain, kind]
    decision = None
    if domain == "mobs" and kind in ("maturation", "reproduction"):
        ticket = payload["ticket"]
        decision = base + [
            {
                key: ticket[key]
                for key in (
                    "map_id",
                    "instance_id",
                    "group_id",
                    "monster_id",
                    "reference",
                    "cycle",
                )
            }
        ]
    elif domain == "plants" and kind == "affinity_reconcile":
        operations = payload.get("original_operations")
        if not isinstance(operations, list) or not 1 <= len(operations) <= 16:
            raise ValueError("Invalid affinity reconciliation identity batch")
        if any(
            type(payload.get(key)) is not int or not 0 < payload[key] < 2**63
            for key in ("account_id", "character_id")
        ):
            raise ValueError("Invalid affinity reconciliation owner identity")
        pairs = []
        for operation in operations:
            if not isinstance(operation, dict):
                raise ValueError("Invalid affinity reconciliation receipt identity")
            name, fingerprint = operation.get("operation"), operation.get(
                "receipt_sha256"
            )
            if (
                not isinstance(name, str)
                or not 1 <= len(name) <= 128
                or not isinstance(fingerprint, str)
                or len(fingerprint) != 64
                or any(character not in "0123456789abcdef" for character in fingerprint)
            ):
                raise ValueError("Invalid affinity reconciliation receipt identity")
            pairs.append((name, fingerprint))
        if len({name for name, _ in pairs}) != len(pairs):
            raise ValueError("Duplicate affinity reconciliation receipt identity")
        decision = base + [
            payload["account_id"],
            payload["character_id"],
            sorted(pairs),
        ]
    elif domain == "plants" and kind == "resource_growth":
        expected = payload["expected"]
        decision = base + [expected["resource_uid"], expected["stage"]]
    elif domain == "plants" and kind in ("planting_begin", "planting_rejected"):
        # A rejected and an accepted plan are alternatives for the same intent.
        decision = [row["world_epoch"], domain, "planting_intent", payload["intent_id"]]
    elif domain == "plants" and kind in (
        "growth_publish",
        "mineral_refill",
        "fishing_refill",
    ):
        decision = base + [payload["resource_uid"], payload.get("available_at")]
    if decision is not None:
        key = _digest(decision)
        return key, key, key
    if domain == "bonuses" and kind == "regional_snapshot":
        slot = base + [payload["map_id"], payload["instance_id"]]
        version = [payload["revision"], payload["regions"]]
        return _digest(slot), _digest(version), None
    if domain == "mobs" and kind == "wander_bulk":
        slot = base + [payload["scope"]]
        version = [
            payload["configuration"],
            sorted(
                (
                    [group["group_id"], group["expected_members"]]
                    for group in payload["moves"]
                ),
                key=lambda group: group[0],
            ),
        ]
        return _digest(slot), _digest(version), None
    if domain == "mobs" and kind in (
        "wander",
        "publish_maturation",
        "publish_reproduction",
    ):
        slot = base + [payload["scope"], payload["group_id"]]
        return _digest(slot), _digest(payload["expected_members"]), None
    # Unknown operations retain their exact existing identity; never collapse
    # distinct weather revisions, corpse expiries or initial-population receipts.
    return row["id"], row["id"], None
