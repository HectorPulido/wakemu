"""Database-configured equilibrium rules requested for this emulator."""


def bounds(value):
    if type(value) is not dict or set(value) != {"minimum", "maximum"}:
        raise ValueError("Invalid ecological population bounds")
    low, high = value["minimum"], value["maximum"]
    if type(low) is not int or type(high) is not int or not 0 <= low <= high < 2**31:
        raise ValueError("Invalid ecological population bounds")
    return low, high


def decision(db, *, map_id, region_id, kind, family_id, action, before, amount=1):
    """Caller supplies authoritative pre-action count under its population lock.

    Improving distance to the equilibrium band earns Wakfu. Worsening it
    earns Stasis; neutral actions do not farm affinity inside the band.
    """
    for number in (map_id, region_id, family_id):
        if type(number) is not int or not 0 < number < 2**31:
            raise ValueError("Invalid ecology scope")
    if kind not in ("plant", "monster") or action not in ("plant", "remove", "harvest"):
        raise ValueError("Invalid ecological action")
    if type(before) is not int or not 0 <= before < 2**31:
        raise ValueError("Invalid ecological population")
    if type(amount) is not int or not 0 < amount < 2**31:
        raise ValueError("Invalid ecological population change")
    after = (
        before
        if action == "harvest"
        else before + amount
        if action == "plant"
        else before - amount
    )
    if not 0 <= after < 2**31:
        raise ValueError("Ecological population change out of range")
    row = db.execute(
        "SELECT value FROM settings WHERE name='personal_ecology_policy'"
    ).fetchone()
    policy = None if row is None else row["value"]
    if type(policy) is not dict or set(policy) != {
        "version",
        "unit",
        "balance_delta",
        "imbalance_delta",
        "plant",
        "monster",
    }:
        raise ValueError("Invalid personal ecology policy")
    if (
        type(policy["version"]) is not int
        or policy["version"] != 2
        or policy["unit"] != "basis_points"
    ):
        raise ValueError("Invalid personal ecology policy version")
    for name, low, high in (("balance_delta", 1, 9900), ("imbalance_delta", -9900, -1)):
        if type(policy[name]) is not int or not low <= policy[name] <= high:
            raise ValueError("Invalid personal ecology delta")
    for population_kind in ("plant", "monster"):
        bounds(policy[population_kind])
    limit = db.execute(
        "SELECT minimum,maximum,source,revision FROM ecology_family_limits "
        "WHERE map_id=%s AND region_id=%s AND kind=%s AND family_id=%s",
        (map_id, region_id, kind, family_id),
    ).fetchone()
    minimum, maximum = bounds(
        policy[kind]
        if limit is None
        else {key: limit[key] for key in ("minimum", "maximum")}
    )
    distance_before = max(minimum - before, before - maximum, 0)
    distance_after = max(minimum - after, after - maximum, 0)
    delta = (
        policy["balance_delta"]
        if distance_after < distance_before
        else policy["imbalance_delta"]
        if distance_after > distance_before
        else 0
    )
    return {
        "delta": delta,
        "evidence": {
            "map_id": map_id,
            "region_id": region_id,
            "kind": kind,
            "family_id": family_id,
            "action": action,
            "before_population": before,
            "after_population": after,
            "distance_before": distance_before,
            "distance_after": distance_after,
            "minimum": minimum,
            "maximum": maximum,
            "limit_source": "local_fallback" if limit is None else limit["source"],
            "limit_revision": None if limit is None else limit["revision"],
            "policy": policy,
        },
    }
