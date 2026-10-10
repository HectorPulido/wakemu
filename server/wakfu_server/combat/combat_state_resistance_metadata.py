"""Original class-scoped fyW.elk modes and explicitly attested null lookups."""
from wakfu_server import native_catalog as protocol_catalog
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_state_resistance_catalog():
    data = protocol_catalog.load(DATA_ROOT / "native-class-state-resistance.json")
    if (
        data.get("schema") != "native-class-state-resistance-v1"
        or data.get("seed_identity", {}).get("schema")
        != "native-class-state-resistance-seeds-v1"
        or data.get("provenance", {}).get("original_inputs_stable") is not True
    ):
        raise ValueError("Missing original class state resistance provenance")
    seeds = data["seed_identity"]["state_ids"]
    states = data.get("states")
    missing = data.get("missing_state_ids")
    enums = data.get("enum_ordinals")
    if (
        not isinstance(seeds, list)
        or len(seeds) != len(set(seeds))
        or any(type(value) is not int or value <= 0 for value in seeds)
        or not isinstance(states, dict)
        or not isinstance(missing, list)
        or any(type(value) is not int or value <= 0 for value in missing)
        or len(missing) != len(set(missing))
        or not isinstance(enums, dict)
        or set(enums) != {"NEGATIF", "NEUTRAL", "POSITIF"}
        or any(type(value) is not int for value in enums.values())
        or set(enums.values()) != {0, 1, 2}
        or set(map(int, states)) | set(missing) != set(seeds)
        or set(map(int, states)) & set(missing)
        or data.get("native_level_checks") != len(states) * 6
    ):
        raise ValueError("Incomplete native class state resistance domain")
    for row in states.values():
        mode = row.get("native_resistance_mode", {})
        if (
            row.get("native_getter") != "fyW.elk"
            or mode.get("enum_class") != "fza"
            or mode.get("name") not in enums
            or type(mode.get("ordinal")) is not int
            or mode.get("ordinal") != enums[mode["name"]]
        ):
            raise ValueError("Invalid native state resistance mode")
    return data


def native_state_absence_proven(reference):
    """Distinguish an original null fyZ lookup from an unexported definition."""
    if type(reference) is not int or reference <= 0:
        raise ValueError("Explicit native state reference required")
    return reference in native_state_resistance_catalog()["missing_state_ids"]


def native_state_resistance_mode(reference):
    if type(reference) is not int or reference <= 0:
        raise ValueError("Explicit native state reference required")
    row = native_state_resistance_catalog()["states"].get(str(reference))
    if row is None:
        raise ValueError("Native state resistance mode outside proven class domain")
    return dict(row["native_resistance_mode"])
