"""Prefer an ordinary effectful attack for the existing atomic AI smoke gate."""


def select(monster):
    witnesses = []
    for case in monster.get("cases", []):
        if case.get("status") != "validated":
            continue
        for target in case.get("successful_targets", []):
            if target.get("effectful") is not True:
                continue
            ordinary_damage = (
                target.get("scenario") is None
                and target.get("target_id") == 7
                and "damage" in target.get("event_kinds", [])
            )
            witnesses.append((not ordinary_damage, case, target))
    if not witnesses:
        raise ValueError("Missing validated effectful native AI witness")
    _, case, target = min(witnesses, key=lambda w: w[0])
    return case, target
