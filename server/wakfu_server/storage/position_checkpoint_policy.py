"""PostgreSQL-owned cadence and start budgets for World position checkpoints."""
import math

SETTING_NAME = "world_position_checkpoint_policy"
REFRESH_SECONDS = 60.0


def validate_policy(value):
    if not isinstance(value, dict):
        raise ValueError("Position checkpoint policy must be an object")
    result = {}
    for name, low, high in (("interval_seconds", 0.1, 30), ("max_seconds", 0.01, 10)):
        number = value.get(name)
        if (
            type(number) not in (int, float)
            or not math.isfinite(number)
            or not low <= number <= high
        ):
            raise ValueError("Invalid position checkpoint " + name)
        result[name] = float(number)
    count = value.get("max_accounts")
    if type(count) is not int or not 1 <= count <= 4096:
        raise ValueError("Invalid position checkpoint max_accounts")
    result["max_accounts"] = count
    return result


def load_policy(store):
    with store.connection(timeout=0.25) as db:
        db.execute("SET LOCAL statement_timeout = '1000ms'")
        row = db.execute(
            "SELECT value FROM settings WHERE name=%s", (SETTING_NAME,)
        ).fetchone()
    if row is None:
        raise ValueError("Missing database setting: " + SETTING_NAME)
    return validate_policy(row["value"])
