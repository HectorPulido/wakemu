"""Shared admission-only minimum-level policy for dungeons and rifts.

The native minimum remains catalog metadata. This policy never changes a
character's real/effective level, modulation, difficulty, rewards or stats.
"""
SETTING = "instance_entry_level_policy"
DEFAULT = {"version": 1, "enforce_minimum_level": False}


def enforced(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    value = None if row is None else row["value"]
    if (
        not isinstance(value, dict)
        or set(value) != set(DEFAULT)
        or type(value.get("version")) is not int
        or value["version"] != 1
        or type(value.get("enforce_minimum_level")) is not bool
    ):
        raise ValueError("Missing or invalid instance entrance level policy")
    return value["enforce_minimum_level"]


def minimum_level_allowed(real_level, native_minimum, *, enforce_minimum):
    if (
        type(real_level) is not int
        or real_level < 1
        or type(native_minimum) is not int
        or native_minimum < 0
        or type(enforce_minimum) is not bool
    ):
        raise ValueError("Invalid instance entrance level authority")
    return not enforce_minimum or real_level >= native_minimum
