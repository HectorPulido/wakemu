"""Materialize database-owned completion rewards once, including old completions."""
import hashlib
import json
import secrets
from psycopg.types.json import Jsonb
from . import catalog

SETTING = "custom_task_completion_reward_policies"


def _policies(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None or type(row["value"]) is not list:
        raise ValueError("Missing database custom task completion reward policies")
    seen = set()
    for policy in row["value"]:
        if type(policy) is not dict or set(policy) != {
            "key",
            "task_key",
            "enabled",
            "kamas",
            "item_references",
            "item_quantity",
            "description",
        }:
            raise ValueError("Invalid custom task completion reward policy")
        key = catalog.key(policy["key"])
        catalog.key(policy["task_key"])
        catalog.text(policy["description"], 4096)
        if key in seen or type(policy["enabled"]) is not bool:
            raise ValueError("Duplicate or invalid completion reward policy")
        seen.add(key)
        if type(policy["kamas"]) is not int or not 0 < policy["kamas"] < 2**63:
            raise ValueError("Invalid completion reward kamas")
        refs = policy["item_references"]
        if type(refs) is not list or not 1 <= len(refs) <= 1000:
            raise ValueError("Invalid completion reward item pool")
        for reference in refs:
            catalog.positive(reference)
        if len(set(refs)) != len(refs):
            raise ValueError("Duplicate completion reward item reference")
        catalog.positive(policy["item_quantity"])
    return row["value"]


def _native_pool(db, policy):
    row = db.execute(
        "SELECT d.raw,d.sha256,d.revision FROM native_catalog_documents d "
        "JOIN native_catalog_active a USING(revision) "
        "JOIN native_catalog_releases r USING(revision) "
        "WHERE a.id=1 AND r.complete AND d.path='item-equipment-effects.json'"
    ).fetchone()
    if row is None:
        raise ValueError("Missing database equipment catalog for completion reward")
    raw = bytes(row["raw"])
    if hashlib.sha256(raw).hexdigest() != row["sha256"]:
        raise ValueError("Completion reward equipment catalog SHA mismatch")
    document = json.loads(raw)
    items = {item["reference"]: item for item in document["items"]}
    for reference in policy["item_references"]:
        item = items.get(reference)
        if item is None or type(item.get("name")) is not str or not item["name"]:
            raise ValueError("Completion reward item lacks native equipment authority")
    return row["revision"], row["sha256"]


def materialize(db, character_id):
    """Caller holds live owned character lock and authorized selected session.

    Random choice is persisted with its exact policy/catalog before delivery.
    Reconnect, capacity retries and configuration edits never reroll an existing
    policy receipt. Changing reward policy does not change earned objective facts.
    """
    rules = catalog.load(db)
    created = []
    for policy in _policies(db):
        if not policy["enabled"] or policy["task_key"] not in rules:
            continue
        progress = db.execute(
            "SELECT completed_at,definition_signature FROM character_custom_task_progress "
            "WHERE character_id=%s AND task_key=%s",
            (character_id, policy["task_key"]),
        ).fetchone()
        if progress is None or progress["completed_at"] is None:
            continue
        if progress["definition_signature"] != catalog.signature(
            rules[policy["task_key"]]
        ):
            raise ValueError("Completion reward objective signature mismatch")
        identity = (character_id, policy["task_key"], policy["key"])
        if db.execute(
            "SELECT 1 FROM character_custom_task_policy_rewards WHERE "
            "character_id=%s AND task_key=%s AND policy_key=%s",
            identity,
        ).fetchone():
            continue
        revision, native_sha = _native_pool(db, policy)
        reference = secrets.choice(policy["item_references"])
        index = db.execute(
            "SELECT COALESCE(max(reward_index),-1)+1 AS next_index "
            "FROM character_custom_task_reward_outbox "
            "WHERE character_id=%s AND task_key=%s",
            identity[:2],
        ).fetchone()["next_index"]
        if index + 1 >= 2**31:
            raise ValueError("Custom task reward index overflow")
        snapshot = {
            "policy": policy,
            "item_reference": reference,
            "catalog_revision": revision,
            "catalog_sha256": native_sha,
            "reward_indices": [index, index + 1],
        }
        db.execute(
            "INSERT INTO character_custom_task_policy_rewards "
            "(character_id,task_key,policy_key,snapshot) VALUES (%s,%s,%s,%s)",
            (*identity, Jsonb(snapshot)),
        )
        for reward_index, payload in (
            (index, {"kind": "kamas", "amount": policy["kamas"]}),
            (index + 1, {"aeV": 5, "ckl": [reference, policy["item_quantity"]]}),
        ):
            db.execute(
                "INSERT INTO character_custom_task_reward_outbox "
                "(character_id,task_key,reward_index,payload) VALUES (%s,%s,%s,%s)",
                (character_id, policy["task_key"], reward_index, Jsonb(payload)),
            )
        created.append(policy["key"])
    return created


def notices(db):
    """Present enabled reward descriptions from the same database policy."""
    result = {}
    for policy in _policies(db):
        if policy["enabled"]:
            result.setdefault(policy["task_key"], []).append(policy["description"])
    return {key: "\n".join(values) for key, values in result.items()}
