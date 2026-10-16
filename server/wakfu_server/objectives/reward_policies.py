"""Versioned level-band rewards expanded into frozen native entitlements."""
import hashlib
import json
import secrets
from psycopg.types.json import Jsonb
from .catalog import integer, key, validate_reward


def validate_policy(policy):
    if (
        type(policy) is not dict
        or set(policy) != {"bands"}
        or type(policy["bands"]) is not list
        or not policy["bands"]
    ):
        raise ValueError("Reward policy requires level bands")
    expected = 1
    for band in policy["bands"]:
        if type(band) is not dict or set(band) != {"minimum", "maximum", "rewards"}:
            raise ValueError("Invalid reward band")
        if (
            integer(band["minimum"], 200) != expected
            or integer(band["maximum"], 200) < expected
        ):
            raise ValueError(
                "Reward bands must cover levels 1 through 200 without gaps or overlaps"
            )
        expected = band["maximum"] + 1
        if (
            type(band["rewards"]) is not list
            or not band["rewards"]
            or len(band["rewards"]) > 32
        ):
            raise ValueError("Reward band requires bounded rewards")
        for reward in band["rewards"]:
            if type(reward) is not dict:
                raise ValueError("Invalid band reward")
            if reward.get("kind") == "scaled":
                raise ValueError("Nested reward policy references are forbidden")
            validate_reward(reward)
    if expected != 201:
        raise ValueError("Reward bands must cover levels 1 through 200")
    return policy


def list_policies(db):
    return db.execute(
        "SELECT * FROM objectives_reward_policies ORDER BY key"
    ).fetchall()


def put_policy(db, policy_key, policy, expected_revision, operator="api"):
    from .repository import ConflictError

    key(policy_key)
    validate_policy(policy)
    if type(expected_revision) is not int or expected_revision < 0:
        raise ValueError("Invalid expected revision")
    db.execute("SELECT pg_advisory_xact_lock(747117401)")
    prior = db.execute(
        "SELECT revision FROM objectives_reward_policies WHERE key=%s FOR UPDATE",
        (policy_key,),
    ).fetchone()
    if (prior["revision"] if prior else 0) != expected_revision:
        raise ConflictError("Reward policy revision changed")
    native_items(db, policy)
    row = db.execute(
        "INSERT INTO objectives_reward_policies(key,policy,revision) VALUES(%s,%s,1) ON CONFLICT(key) DO UPDATE SET policy=EXCLUDED.policy,revision=objectives_reward_policies.revision+1,updated_at=CURRENT_TIMESTAMP RETURNING *",
        (policy_key, Jsonb(policy)),
    ).fetchone()
    db.execute(
        "INSERT INTO objectives_reward_policy_audit(policy_key,revision,operator,policy) VALUES(%s,%s,%s,%s)",
        (policy_key, row["revision"], str(operator)[:256], Jsonb(policy)),
    )
    return row


def native_items(db, policy):
    """Check exact published authority, never infer sublimation power from level 1."""
    documents = {}
    for path in ("item-stack-rules.json", "item-equipment-rules.json"):
        row = db.execute(
            "SELECT d.raw,d.sha256 FROM native_catalog_documents d JOIN native_catalog_active a USING(revision) JOIN native_catalog_releases r USING(revision) WHERE a.id=1 AND r.complete AND d.path=%s",
            (path,),
        ).fetchone()
        if (
            row is None
            or hashlib.sha256(bytes(row["raw"])).hexdigest() != row["sha256"]
        ):
            raise ValueError("Missing or invalid native reward item authority")
        documents[path] = json.loads(bytes(row["raw"]))
    stacks = documents["item-stack-rules.json"]
    equipment = documents["item-equipment-rules.json"]
    stacks = stacks.get("items", stacks) if type(stacks) is dict else stacks
    equipment = (
        equipment.get("items", equipment) if type(equipment) is dict else equipment
    )

    def indexed(value):
        if type(value) is dict:
            return {int(k): v for k, v in value.items()}
        return {entry["reference"]: entry for entry in value}

    stack_by_ref, equipment_by_ref = indexed(stacks), indexed(equipment)
    for band in policy["bands"]:
        for reward in band["rewards"]:
            references = (
                reward.get("references", [])
                if reward.get("kind") == "random_item"
                else ([reward["ckl"][0]] if reward.get("aeV") == 5 else [])
            )
            if any(ref not in stack_by_ref for ref in references):
                raise ValueError("Reward item lacks native stack authority")
    return equipment_by_ref


def expand(db, policy_row, level):
    integer(level, 200)
    policy = validate_policy(policy_row["policy"])
    equipment = native_items(db, policy)
    band = next(b for b in policy["bands"] if b["minimum"] <= level <= b["maximum"])
    rewards = []

    def eligible(reference):
        item = equipment.get(reference)
        return item is None or item.get("minimum_level", item.get("level", 0)) <= level

    for reward in band["rewards"]:
        if reward.get("kind") == "random_item":
            pool = [
                reference for reference in reward["references"] if eligible(reference)
            ]
            if pool:
                rewards.append(
                    {"aeV": 5, "ckl": [secrets.choice(pool), reward["quantity"]]}
                )
        elif reward.get("aeV") == 5 and not eligible(reward["ckl"][0]):
            raise ValueError("Reward equipment exceeds frozen source level")
        else:
            rewards.append(reward)
    return rewards
