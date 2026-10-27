"""Source-backed fbc TRAP constructor and native eRF characteristic subset."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_parameters import _float32


@lru_cache(maxsize=1)
def trap_characteristics():
    return protocol_catalog.load(DATA_ROOT / "native-trap-characteristics.json")


def trap_constructor(definition):
    if (
        definition.get("type") != "TRAP"
        or definition.get("native_class") != "bcY"
        or definition.get("native_type_id") != 3
        or definition.get("native_container_type") != 3
    ):
        raise ValueError("Missing native fbc trap prototype")
    raw = definition.get("raw_bdh")
    if not isinstance(raw, (list, tuple)) or any(
        type(v) not in (int, float) for v in raw
    ):
        raise ValueError("Missing native fbc constructor parameters")
    parameters = tuple(_float32(v) for v in raw)
    return dict(
        owner_activation=bool(parameters and parameters[0] == 1),
        fqx=len(parameters) < 2 or parameters[1] == 0,
        characteristic_ids=tuple(
            sorted(int(k) for k in trap_characteristics()["characteristics"])
        ),
        parameters=parameters,
        source="fbc.aQc.eRF_rMB",
    )


def install_trap_characteristics(row, definition):
    row["native_trap_constructor"] = trap_constructor(definition)
    row["native_trap_characteristics"] = {
        int(k): v["current"]
        for k, v in trap_characteristics()["characteristics"].items()
    }
    row["native_trap_characteristic_source"] = "fbc.aQc.eRF_rMB"


def verified_trap_characteristics(row, definition):
    if (
        row.get("native_area_contract") != "fbc"
        or row.get("native_trap_constructor") != trap_constructor(definition)
        or row.get("native_trap_characteristic_source") != "fbc.aQc.eRF_rMB"
    ):
        raise ValueError("Missing actual native fbc constructor")
    values = row.get("native_trap_characteristics")
    definitions = trap_characteristics()["characteristics"]
    if (
        not isinstance(values, dict)
        or set(values) != {int(k) for k in definitions}
        or any(
            type(v) is not int
            or not definitions[str(k)]["minimum"] <= v <= definitions[str(k)]["maximum"]
            for k, v in values.items()
        )
    ):
        raise ValueError("Missing actual native fbc characteristic values")
    return values


def trap_pa_pair(row, definition, characteristic):
    """Return the actual trap PA current and native constructor maximum.

    eRF creates each fbc.rMB PA through eRC.f. The published native probe reads
    PA.aYU for its maximum separately from aYS current. Supported trap copying
    mutates only current via nG; it does not replace the constructor maximum.
    Missing PCs are the original eRF.b null, never a fabricated zero pair.
    """
    if type(characteristic) is not int or not 0 <= characteristic <= 255:
        raise ValueError("Invalid native trap PA characteristic")
    current = verified_trap_characteristics(row, definition)
    if characteristic not in current:
        return None
    bounds = trap_characteristics()["characteristics"][str(characteristic)]
    maximum = bounds.get("maximum")
    if (
        type(maximum) is not int
        or not -(1 << 31) <= maximum < (1 << 31)
        or maximum > bounds["hard_maximum"]
        or maximum < bounds["minimum"]
    ):
        raise ValueError("Missing native trap PA constructor maximum")
    return current[characteristic], maximum


def trap_owner_movement_allowed(row, definition, *, target_id, current_id, event_ids):
    verified_trap_characteristics(row, definition)
    if (
        row["native_trap_constructor"]["owner_activation"]
        or target_id != row["owner_id"]
    ):
        return True
    if not set(event_ids).intersection((10001, 10008, 10002)):
        return True
    return current_id != row["owner_id"]  # Exact fbc.e rMD/rMz + SU.ex guard.


def retire_exhausted_trap(fight, row, *, callbacks):
    """Wakemu cleanup caller for native Qq.baD after successful activation."""
    if row.get("native_area_contract") != "fbc":
        return False
    remaining = row.get("remaining_activations")
    executing = row.get("executing")
    if type(remaining) is not int or type(executing) is not bool:
        raise ValueError("Missing native Qq.baD activation fields")
    if remaining != 0 or executing:
        return False
    if getattr(fight, "native_effect_areas", {}).get(row["uid"]) is not row:
        return False  # An activation child already removed the actual area.
    row["native_exhausted_retirement_policy"] = "wakemu.successful-activation.Qq.baD-v1"
    # Retiring only the Qs area leaves its eYW application on the owner's Qf
    # and therefore leaves the trap drawn on every client. Unapply that actual
    # parent through the shared retained removal path as mask removal does.
    callbacks.remove_parent(row)
    return True
