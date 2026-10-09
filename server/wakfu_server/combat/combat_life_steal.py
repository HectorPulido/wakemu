"""Native eXv/24: life-steal healing, not ordinary elemental mastery healing."""
from wakfu_server import native_catalog as protocol_catalog
import math
from .combat_parameters import parameter_value
from wakfu_server.equipment_damage import _float
from .combat_effect_removal import _identity_fields


def life_steal_amount(parameters, level, source_stats, target_stats, context=None):
    if len(parameters) not in (2, 4):
        raise ValueError("Unaudited native life-steal parameter count")
    amount = parameter_value(parameters, 0, level)
    bonus_enabled = len(parameters) == 2 or parameter_value(parameters, 1, level) != 0
    if context is not None:
        if not isinstance(context, bytes):
            raise ValueError("Invalid life-steal context")
        fields = _identity_fields(context, integer_fields=(6,))
        override = fields.get(6, 0)
        override = (override + (1 << 31)) % (1 << 32) - (1 << 31)
        if override:
            amount = override
    value = _float(amount)
    if bonus_enabled:
        bonus = source_stats.get(53)
        if type(bonus) is not int:
            raise ValueError("Missing native LIFE_STOLEN_BONUS authority")
        value = _float(
            _float(value * _float(_float(100) + _float(bonus))) / _float(100)
        )
    resistance = target_stats.get(32)
    if type(resistance) is not int:
        raise ValueError("Missing native healing resistance authority")
    value = _float(value - _float(_float(value * _float(resistance)) / _float(1000)))
    # GS.B: Java float->int saturation, then subtract1 only for negative fractions.
    if math.isnan(value):
        rounded = 0
    else:
        rounded = max(-(1 << 31), min((1 << 31) - 1, math.trunc(value)))
    if value < 0 and _float(rounded) != value:
        rounded = (rounded - 1 + (1 << 31)) % (1 << 32) - (1 << 31)
    return max(0, rounded)


from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT


@lru_cache(maxsize=1)
def native_spell_elements():
    return protocol_catalog.load(DATA_ROOT / "native-spell-elements.json")["spells"]


def life_steal_event_ids(retention, invocation):
    """eXv.bbx has0/1/20; eZR.bby falls back only to fyG type11."""
    descriptor, identity = retention.container(invocation)
    present = descriptor.get("container_present")
    if type(present) is not bool:
        raise ValueError("Missing native life-steal container presence")
    ids = {0, 1, 20}
    if present:
        kind = descriptor.get("container_type")
        if type(kind) is not int:
            raise ValueError("Missing native life-steal container kind")
        if kind == 11:
            if type(identity) is not int or identity <= 0:
                raise ValueError("Missing native fyG packed identity")
            reference = identity >> 16
            row = native_spell_elements().get(str(reference))
            if row is None:
                raise ValueError("Missing native fyF element metadata")
            event = row["event_id"]
            if event is not None:
                if type(event) is not int or event < 0:
                    raise ValueError("Invalid native element event")
                ids.add(event)
    return tuple(sorted(ids))
