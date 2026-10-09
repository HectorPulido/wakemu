"""Original fan current-then-maximum scaling for captured class summons."""
import math

from .combat_parameters import _float32
from .combat_maximum_resource import _snapshot, effective_maximum
from .combat_parameter_maximum import _write
from .combat_actor_snapshot import native_actor_catalog

# Original fan.rJJ/rJK iteration, exported from the installed enum identities.
MAIN_CHARACTERISTICS = (1, 92, 24, 21, 23, 22, 20, 31, 28, 30, 29, 27)
SECONDARY_CHARACTERISTICS = (8, 7, 35)


def _round(value):
    if math.isnan(value):
        return 0
    if value <= -2147483648:
        return -2147483648
    if value >= 2147483647:
        return 2147483647
    return math.floor(value + 0.5)


def scaled_characteristic(current, maximum, factor):
    if type(factor) not in (int, float):
        raise ValueError("Missing actual native fan scaling factor")
    factor = _float32(factor)
    current_float = _float32(current)
    reduction = abs(_float32(current_float * _float32(1.0 - factor)))
    return (
        _round(_float32(current_float - reduction)),
        _round(_float32(_float32(maximum) * factor)),
    )


def scale_captured_characteristics(preview, actor, main_factor, secondary_factor):
    """Preflight all PA snapshots, then publish original fan setter order."""
    if preview.actors.get(actor.id) is not actor:
        raise ValueError(
            "Captured fan requires the actual registered constructor result"
        )
    source = getattr(actor, "native_summon_source", None)
    if (
        not isinstance(source, dict)
        or source.get("native_relation_source")
        != "big.new_bje.fdt_initial_registration"
    ):
        raise ValueError("Missing actual captured bje constructor provenance")
    definitions = native_actor_catalog()["characteristics"]
    updates = []
    for group, factor in (
        (MAIN_CHARACTERISTICS, main_factor),
        (SECONDARY_CHARACTERISTICS, secondary_factor),
    ):
        for stat in group:
            current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
                actor, stat
            )
            requested, scaled_maximum = scaled_characteristic(current, maximum, factor)
            row = definitions[str(stat)]
            # PA.on runs with the original maximum; expandable PA uses hard max.
            current = max(
                minimum, min(high if row["expandable"] else maximum, requested)
            )
            # PA.or sets RAW max to scaled EFFECTIVE max, retaining percentage.
            raw = max(raw_min, scaled_maximum)
            maximum = effective_maximum(raw, percent, low, high)
            if not row["expandable"]:
                current = min(current, maximum)
            updates.append((stat, current, raw, maximum))
    for stat, current, raw, maximum in updates:
        _write(actor, stat, current, raw, maximum)
    return tuple(updates)
