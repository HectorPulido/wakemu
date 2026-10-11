"""Staged native-compatible planting balance; no client override is assumed.

The policy supplies effect2000 bonus points, not a replacement terrain curve.
Activation requires publishing the same bonus to the native actor. Keep the
open profile independent until its hardcoded visual override is disabled.
"""

DEFAULT_POLICY = dict(version=1, levels_per_point=2, maximum_level_bonus=100)


def validate(policy):
    if (
        not isinstance(policy, dict)
        or set(policy) != set(DEFAULT_POLICY)
        or any(type(value) is not int for value in policy.values())
        or policy["version"] != 1
        or not 1 <= policy["levels_per_point"] <= 1000
        or not 0 <= policy["maximum_level_bonus"] <= 100
    ):
        raise ValueError("Invalid native planting level bonus policy")
    return dict(policy)


def bonus(profession_level, *, authoritative_bonus=0, policy=None):
    """Integer points consumed by eRN for PLANTATION_PROBABILTY/context2."""
    policy = validate(DEFAULT_POLICY if policy is None else policy)
    if type(profession_level) is not int or not 0 <= profession_level <= 32767:
        raise ValueError("Invalid authoritative planting profession level")
    if type(authoritative_bonus) is not int:
        raise ValueError("Invalid authoritative planting effect bonus")
    result = (
        min(
            policy["maximum_level_bonus"],
            profession_level // policy["levels_per_point"],
        )
        + authoritative_bonus
    )
    if not -(1 << 31) <= result < (1 << 31):
        raise ValueError("Native planting bonus exceeds signed int32")
    return result


def load(db):
    row = db.execute(
        "SELECT value FROM settings WHERE name='planting_level_bonus'"
    ).fetchone()
    return validate(None if row is None else row["value"])


def account_bonuses(db, account_id, *, authoritative_bonuses=None):
    """Read SQL-owned levels for a proposed matching actor publication.

    This function does not activate the proposal or trust character/client
    profession levels. Additional bonuses must come from an authoritative
    effect resolver; absent effects are explicitly zero.
    """
    from wakfu_server.profession_wire import level

    if type(account_id) is not int or account_id <= 0:
        raise ValueError("Invalid planting bonus account")
    additional = {} if authoritative_bonuses is None else authoritative_bonuses
    policy = load(db)
    return {
        row["profession_id"]: bonus(
            level(row["xp"]),
            authoritative_bonus=additional.get(row["profession_id"], 0),
            policy=policy,
        )
        for row in db.execute(
            "SELECT profession_id,xp FROM account_professions "
            "WHERE account_id=%s ORDER BY profession_id",
            (account_id,),
        )
    }


def resolver(store):
    """Staged provider; activate only with matching native bonus publication."""

    def resolve(prepared):
        with store.connection() as db:
            bonuses = account_bonuses(db, prepared["character"]["account_id"])
        profession = prepared["seed"]["profession_id"]
        if profession not in bonuses:
            raise ValueError("Planting bonus profession is not learned")
        return bonuses[profession]

    return resolve
