"""Shared collaborative goal: original authority first, declared fallback second.

The user-authorized fallback is four times the original personal requirement,
not four times credited progress. Population remains inventory, except where
an original objective explicitly uses spawned population (native herd goals).
"""
import re

from .environmental_runtime import integer


FALLBACK_MULTIPLIER = 4
_GLOBAL_MINIMUMS = ("nbMobMin", "nbResourceMin")


def target(db, profile):
    """Return a qualified shared minimum, or None for other goal contracts."""
    if profile["mode"] != "collaborative":
        return None
    rows = db.execute(
        "SELECT b.*,p.native_scenario_id AS policy_scenario,p.policy_contract,"
        "c.normalized_key,c.native_value "
        "FROM environmental_profile_native_variable_policy p "
        "JOIN environmental_profile_native_variable_bindings b "
        "ON (b.profile_key,b.version,b.source_key,b.native_scenario_id)="
        "(p.profile_key,p.version,p.source_key,p.native_scenario_id) "
        "LEFT JOIN environmental_native_configuration c ON "
        "(c.source_key,c.scenario_id,c.native_key)="
        "(b.source_key,b.native_scenario_id,b.configuration_key) "
        "WHERE p.profile_key=%s AND p.version=%s "
        "AND b.native_name=ANY(%s)",
        (profile["profile_key"], profile["version"], list(_GLOBAL_MINIMUMS)),
    ).fetchall()
    if not rows:
        return None
    if len(rows) != 1 or not profile["sealed"]:
        raise ValueError("Collaborative minimum lacks one frozen source binding")
    row = rows[0]
    if (
        row["policy_scenario"] != profile["native_scenario_id"]
        or row["policy_contract"] != "wakemu.durable-native-variable-projection.v1"
    ):
        raise ValueError("Collaborative minimum differs from its native profile")
    # Reuse the exact source/binding checks already required for native display.
    from .environmental_native_variables import _binding

    _binding(row)
    original = db.execute(
        "SELECT native_value FROM environmental_native_configuration "
        "WHERE source_key=%s AND scenario_id=%s AND normalized_key=%s",
        (row["source_key"], row["native_scenario_id"], row["native_name"].lower()),
    ).fetchall()
    if original:
        if len(original) != 1 or not re.fullmatch(
            r"[0-9]+", original[0]["native_value"]
        ):
            raise ValueError("Unsupported original collaborative minimum")
        return integer(
            int(original[0]["native_value"]), "original shared minimum", minimum=1
        )
    if row["binding_kind"] != "declared_threshold":
        raise ValueError("Collaborative fallback lacks declared source authority")
    personal = integer(row["constant_value"], "original personal minimum", minimum=1)
    if personal != profile["minimum_contribution"]:
        # A separately authored eligibility/goal contract is not this fallback.
        return None
    return integer(personal * FALLBACK_MULTIPLIER, "declared shared minimum", minimum=1)
