"""Freeze full database profile rows once per encounter, inside the AI SDK."""
from copy import deepcopy
import hashlib
import json

from ..context.native_context import encode


def encounter_profiles(runtime, store, monsters):
    cached = getattr(runtime, "native_ai_profiles", None)
    if cached is not None:
        return deepcopy(cached)
    with store.connection() as db:
        db.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        rows = list(
            db.execute(
                """
            SELECT NULL::integer AS monster_reference, v.*
            FROM ai_policy_active a JOIN ai_policy_versions v USING(profile,version)
            UNION ALL
            SELECT m.monster_reference, v.*
            FROM monster_ai_profiles m JOIN ai_policy_versions v USING(profile,version)
            """
            )
        )
    profiles = {}
    for row in rows:
        data = deepcopy(dict(row))
        reference = data["monster_reference"]
        if (
            reference in profiles
            or reference is not None
            and (type(reference) is not int or reference <= 0)
        ):
            raise ValueError("Ambiguous native AI profile binding")
        if (
            not isinstance(data.get("profile"), str)
            or not data["profile"]
            or type(data.get("version")) is not int
            or data["version"] <= 0
            or not isinstance(data.get("policy"), dict)
            or not isinstance(data.get("forecast_limits"), dict)
        ):
            raise ValueError("Invalid native AI profile row")
        policy = deepcopy(data["policy"])
        limits = {
            name: policy[name]
            for name in ("depth", "beam", "nodes", "budgetMs", "alternatives")
            if name in policy
        }
        configured = policy.get("limits", {})
        if not isinstance(configured, dict):
            raise ValueError("Invalid native AI profile limits")
        policy["limits"] = dict(limits, **configured)
        # Preserve the complete database row in runtime, including columns
        # introduced later; normalize only the convenient search envelope.
        digest = hashlib.sha256(
            json.dumps(encode(data), separators=(",", ":"), allow_nan=False).encode()
        ).hexdigest()
        profiles[reference] = dict(
            data=data,
            policy=policy,
            identity=data["profile"] + ":" + str(data["version"]) + ":" + digest,
        )
    if None not in profiles:
        raise ValueError("Missing default native AI profile")
    runtime.native_ai_profiles = deepcopy(profiles)
    return profiles
