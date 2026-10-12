"""Strict configurable local tasks; no installed achievement IDs are borrowed."""
import copy
import hashlib
import json
import re


def positive(value):
    if type(value) is not int or not 0 < value < 2**31:
        raise ValueError("Expected positive signed32 integer")
    return value


def key(value):
    if not isinstance(value, str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9._:-]{0,127}", value
    ):
        raise ValueError("Invalid custom task key")
    return value


def text(value, limit):
    if not isinstance(value, str) or not value or "\0" in value:
        raise ValueError("Invalid custom task text")
    try:
        encoded = value.encode("utf-8")
    except UnicodeError as exc:
        raise ValueError("Invalid custom task UTF-8") from exc
    if len(encoded) > limit:
        raise ValueError("Custom task text exceeds limit")
    return value


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


SETTING = "custom_task_definitions"


def load(db=None):
    """Read database-owned task policy, failing closed without an imported row."""
    if db is None:
        from wakfu_server.storage.native_catalog import _database

        with _database().connection() as connection:
            return load(connection)
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        raise ValueError("Missing database custom task definitions")
    return validate(row["value"])


def validate(definitions=None, *, db=None):
    if definitions is None:
        return load(db)
    source = definitions
    if type(source) is not list or len(source) > 1000:
        raise ValueError("Invalid custom task catalog")
    result = {}
    for source_row in source:
        if type(source_row) is not dict or set(source_row) != {
            "key",
            "title",
            "description",
            "target",
            "enabled",
            "predicate",
            "rewards",
        }:
            raise ValueError("Invalid custom task definition")
        row = copy.deepcopy(source_row)
        identity = key(row["key"])
        if identity in result or type(row["enabled"]) is not bool:
            raise ValueError("Duplicate task key or invalid enable flag")
        text(row["title"], 255)
        text(row["description"], 4096)
        positive(row["target"])
        predicate = row["predicate"]
        if type(predicate) is not dict:
            raise ValueError("Invalid custom task predicate")
        if predicate.get("kind") == "original_monster_killed":
            if set(predicate) != {"kind", "references"}:
                raise ValueError("Invalid original monster predicate")
            refs = predicate["references"]
            if type(refs) is not list or not 1 <= len(refs) <= 10000:
                raise ValueError("Invalid original monster references")
            for reference in refs:
                positive(reference)
            if len(set(refs)) != len(refs):
                raise ValueError("Duplicate original monster reference")
            predicate["references"] = sorted(refs)
        elif predicate.get("kind") == "monster_seed_planted":
            if set(predicate) != {
                "kind",
                "family_id",
                "seed_reference",
                "resource_reference",
            }:
                raise ValueError("Invalid monster seed predicate")
            for field in ("family_id", "seed_reference", "resource_reference"):
                positive(predicate[field])
        else:
            raise ValueError("Unsupported custom task predicate")
        if type(row["rewards"]) is not list or len(row["rewards"]) > 100:
            raise ValueError("Invalid custom task rewards")
        for reward in row["rewards"]:
            if type(reward) is not dict or set(reward) != {"aeV", "ckl"}:
                raise ValueError("Invalid native reward representation")
            kind, params = reward["aeV"], reward["ckl"]
            if type(kind) is not int or kind not in (2, 3, 5, 6):
                raise ValueError("Unsupported native reward kind")
            if type(params) is not list or len(params) != (2 if kind == 5 else 1):
                raise ValueError("Invalid native reward parameters")
            for param in params:
                positive(param)
            if kind == 2 and params[0] > 65535:
                raise ValueError("Native title exceeds unsigned16")
        result[identity] = row
    return result


def signature(definition):
    """Presentation/enable edits preserve progress; new semantics need a new key."""
    payload = {
        field: definition[field] for field in ("key", "predicate", "target", "rewards")
    }
    return hashlib.sha256(canonical(payload).encode("utf-8")).hexdigest()
