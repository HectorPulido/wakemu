"""Literal non-stat guild criterion bonus semantics from fgU/eMq/bkZ.

These bonuses authorize native HasGuildBonus predicates by active identity.
They do not manufacture character effects, equipment statistics or capacity.
"""


def native_descriptor(native):
    """Return the shared permanent criterion descriptor, or no matching route."""
    if not isinstance(native, dict):
        raise ValueError("Invalid native guild bonus definition")
    if native.get("effect_type") != "CRITERION_BONUS":
        return None
    identity = native.get("id")
    if (
        type(identity) is not int
        or not 0 < identity < 2**31
        or native.get("effect_class") != "fgU"
        or native.get("effect_type_id") != 4
        or native.get("effect_parameters") != {}
        or native.get("category") != "CRITERION_BONUS"
        or native.get("has_effect_duration") is not False
        or type(native.get("effect_duration_ms")) is not int
        or native["effect_duration_ms"] != 0
    ):
        raise ValueError("Conflicting native guild criterion bonus definition")
    return dict(kind="criterion_bonus", value=identity, duration_ms=-1)


def active_identity(record, now_ms):
    """fhU.s: defined activation date no later than the native current date."""
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid native guild criterion observation date")
    if record is None:
        return False
    if not isinstance(record, dict) or type(record.get("active")) is not bool:
        raise ValueError("Malformed native guild criterion activation")
    if not record["active"]:
        return False
    activated = record.get("activated_at_ms")
    if type(activated) is not int or activated <= 0:
        raise ValueError("Missing native guild criterion activation date")
    return activated <= now_ms
