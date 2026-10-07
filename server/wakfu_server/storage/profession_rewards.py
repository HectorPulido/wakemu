"""Explicit database-owned emulator balance for successful profession actions."""


def base_xp(db, kind, *, recipe_slots=None):
    row = db.execute(
        "SELECT value FROM settings WHERE name='profession_action_rewards'"
    ).fetchone()
    policy = None if row is None else row["value"]
    keys = {"version", "planting_xp", "harvest_xp", "recipe_slot_xp"}
    if (
        not isinstance(policy, dict)
        or set(policy) != keys
        or type(policy["version"]) is not int
        or policy["version"] != 1
        or any(
            type(policy[key]) is not int or not 0 <= policy[key] <= 3_000_000
            for key in keys - {"version"}
        )
    ):
        raise ValueError("Invalid profession action reward policy")
    if kind in ("planting", "harvest") and recipe_slots is None:
        return policy[kind + "_xp"]
    if kind == "recipe" and type(recipe_slots) is int and 1 <= recipe_slots <= 16:
        return recipe_slots * policy["recipe_slot_xp"]
    raise ValueError("Invalid profession action reward kind")
