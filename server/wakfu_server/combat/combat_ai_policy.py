"""Read and freeze database tactical profiles once per native encounter.

No query per preview. Invalid configuration is rejected before requesting AI;
the caller can end the NPC turn safely, without modifying spell rules.
"""
from copy import deepcopy
import hashlib
import json
import math
import re


SEARCH_LIMITS = {
    "depth": 16,
    "beam": 64,
    "nodes": 4096,
    "budgetMs": 250,
    "alternatives": 16,
}
FORECAST_LIMITS = {"depth": 4, "max_previews": 256, "budget_ms": 5000}
WEIGHTS = frozenset(
    (
        "damage",
        "healing",
        "armor",
        "kills",
        "control",
        "resources",
        "threat",
        "position",
        "coordination",
        "uncertainty",
    )
)


def validate_profile(row):
    profile, version = row["profile"], row["version"]
    if not isinstance(profile, str) or not re.fullmatch(
        r"[a-z][a-z0-9_]{0,63}", profile
    ):
        raise ValueError("Invalid AI profile name")
    if type(version) is not int or not 1 <= version <= 2147483647:
        raise ValueError("Invalid AI profile version")
    policy, forecast = row["policy"], row["forecast_limits"]
    if not isinstance(policy, dict) or set(policy) - {
        "weights",
        "featureWeights",
        *SEARCH_LIMITS,
    }:
        raise ValueError("Invalid AI profile policy")
    if not isinstance(forecast, dict) or set(forecast) - FORECAST_LIMITS.keys():
        raise ValueError("Invalid AI forecast policy")
    for values, limits in ((policy, SEARCH_LIMITS), (forecast, FORECAST_LIMITS)):
        for name, maximum in limits.items():
            if name in values and (
                type(values[name]) is not int or not 1 <= values[name] <= maximum
            ):
                raise ValueError("Invalid AI policy limit: " + name)
    for field in ("weights", "featureWeights"):
        values = policy.get(field, {})
        if not isinstance(values, dict) or len(values) > 64:
            raise ValueError("Invalid AI profile weights")
        for name, value in values.items():
            if (
                not isinstance(name, str)
                or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", name)
                or field == "weights"
                and name not in WEIGHTS
                or type(value) not in (int, float)
                or not math.isfinite(value)
                or not (-1000 if field == "featureWeights" else 0) <= value <= 1000
            ):
                raise ValueError("Invalid AI profile weight")
    canonical = dict(
        profile=profile, version=version, policy=policy, forecast_limits=forecast
    )
    digest = hashlib.sha256(
        json.dumps(
            canonical, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
    ).hexdigest()
    return dict(
        deepcopy(canonical), identity=profile + ":" + str(version) + ":" + digest
    )


def encounter_profiles(runtime, store, monsters):
    cached = getattr(runtime, "tactical_profiles", None)
    if cached is not None:
        return deepcopy(cached)
    references = sorted(
        {
            monsters[a.id]["ref"]
            for a in runtime.fight.actors.values()
            if not a.controlled and a.id in monsters
        }
    )
    with store.connection() as db:
        rows = list(
            db.execute(
                """
            SELECT NULL::integer AS monster_reference, v.profile,v.version,v.policy,v.forecast_limits
            FROM ai_policy_active a JOIN ai_policy_versions v USING(profile,version)
            UNION ALL
            SELECT m.monster_reference,v.profile,v.version,v.policy,v.forecast_limits
            FROM monster_ai_profiles m JOIN ai_policy_versions v USING(profile,version)
            WHERE m.monster_reference = ANY(%s)
            """,
                (references,),
            )
        )
    result = {row["monster_reference"]: validate_profile(row) for row in rows}
    if None not in result:
        raise ValueError("Missing active AI profile")
    # Freeze all initial roster bindings atomically. Later DB edits apply only
    # to a new encounter; a new summon uses the encounter's frozen default.
    runtime.tactical_profiles = deepcopy(result)
    return result
