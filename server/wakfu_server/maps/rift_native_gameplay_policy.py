"""SQL-owned reconstruction metadata; original effect arithmetic stays native."""
from copy import deepcopy

SETTING = "rift_native_gameplay_policy"
POLICY = "wakemu.rift.native-gameplay.v1"


def load(db):
    row = db.execute("SELECT value FROM settings WHERE name=%s", (SETTING,)).fetchone()
    if row is None:
        return None
    value = row["value"]
    if (
        not isinstance(value, dict)
        or value.get("policy") != POLICY
        or value.get("schema_version") != 1
        or type(value.get("enabled")) is not bool
        or value.get("authority") != "native_consumers_with_reconstructed_producers"
        or type(value.get("wave_state")) is not int
        or value["wave_state"] <= 0
        or value.get("wave_grade")
        != "current_wave_number_clamped_to_native_state_maximum"
    ):
        raise ValueError("Invalid native rift gameplay policy")
    return deepcopy(value)
