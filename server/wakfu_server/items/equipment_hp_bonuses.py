"""Pure replay for qualified native eWO maximum/current HP equipment roots."""

from copy import deepcopy

_INT_MIN = -(1 << 31)
_INT_MAX = (1 << 31) - 1


def _int32(value):
    value &= 0xFFFFFFFF
    return value - (1 << 32) if value >= (1 << 31) else value


def descriptor(effect):
    """Parse generic21/eWO HP operations without item allowlists.

    Equipment ownership, slot ordering and item criteria stay with the normal
    build resolver. The native registry binds generic21/eWO to HP even though
    the exporter leaves stat_id=-1. The second operand is eWO's chance; a
    probabilistic operation remains unresolved until the owned equip transaction.
    """
    if not isinstance(effect, dict):
        return None
    values = effect.get("values")
    count = effect.get("parameter_count")
    if not (
        type(effect.get("generic")) is int
        and effect.get("generic") == 21
        and effect.get("runner") == "eWO"
        and type(effect.get("stat_id")) is int
        and effect.get("stat_id") == -1
        and type(count) is int
        and count in (1, 2, 3, 4)
        and isinstance(values, list)
        and len(values) >= count
        and all(
            type(value) is int and _INT_MIN <= value <= _INT_MAX
            for value in values[:count]
        )
        and effect.get("effect_criteria") is False
        and effect.get("has_triggers") is False
        and type(effect.get("target_mask")) is int
        and effect.get("target_mask") == 0
        and type(effect.get("native_variant")) is int
        and effect.get("native_variant") == 0
        and effect.get("native_active_effect") is False
        and type(effect.get("native_execution_mode", 0)) is int
        and effect.get("native_execution_mode", 0) == 0
    ):
        return None
    amount = values[0]
    chance = 100 if count < 2 or values[1] < 0 else max(0, min(100, values[1]))
    if amount < 0:
        return None
    restore_current = count < 3 or values[2] == 1
    reduce_current = count < 4 or values[3] == 1
    operation = dict(
        family="eWO",
        stat=1,
        amount=amount,
        reduce_current=reduce_current,
        restore_current=restore_current,
    )
    if chance != 100:
        operation["chance"] = chance
    return operation


def _clamp(value, low, high):
    return max(low, min(high, value))


def _java_divide(numerator, denominator):
    """Java integer division, which truncates toward zero."""
    if denominator == 0:
        raise ValueError("Invalid HP percentage denominator")
    quotient = abs(numerator) // abs(denominator)
    return -quotient if (numerator < 0) != (denominator < 0) else quotient


def _validated_state(state):
    if not isinstance(state, dict):
        raise ValueError("Native HP state must be a mapping")
    row = deepcopy(state)
    fields = (
        "raw_current",
        "raw_minimum",
        "raw_maximum",
        "hard_minimum",
        "hard_maximum",
        "maximum_percentage",
    )
    if any(
        type(row.get(field, 0 if field == "maximum_percentage" else None)) is not int
        for field in fields
    ):
        raise ValueError("Incomplete native HP state")
    for field in fields:
        value = row.get(field, 0 if field == "maximum_percentage" else None)
        if value < _INT_MIN or value > _INT_MAX:
            raise ValueError("Native HP state exceeds Java int range")
    row.setdefault("maximum_percentage", 0)
    if row["hard_minimum"] > row["hard_maximum"]:
        raise ValueError("Invalid native HP hard bounds")
    if row["raw_minimum"] > row["raw_maximum"]:
        raise ValueError("Invalid native HP raw bounds")
    row.update(_effective_bounds(row))
    if row["raw_current"] < row["minimum"] or row["raw_current"] > row["hard_maximum"]:
        raise ValueError("Native HP current is outside native HP bounds")
    return row


def _effective_bounds(row):
    minimum = _clamp(row["raw_minimum"], row["hard_minimum"], row["hard_maximum"])
    # fff.aYU computes rawMax + (rawMax * percentage / 100) with Java int
    # overflow and truncation, then clamps it to the actor's hard bounds.
    scaled = _int32(row["raw_maximum"] * row["maximum_percentage"])
    adjusted = _int32(row["raw_maximum"] + _java_divide(scaled, 100))
    maximum = _clamp(adjusted, row["hard_minimum"], row["hard_maximum"])
    if minimum > maximum:
        raise ValueError("Invalid native effective HP bounds")
    return dict(minimum=minimum, maximum=maximum)


def _visible_current(row):
    # HP's ffw.fZB is true: aYS() exposes a clamped value even though the raw
    # PA current may remain above an effect-lowered maximum.
    return _clamp(row["raw_current"], row["minimum"], row["maximum"])


def _set_raw_minimum(row, candidate):
    if row["raw_minimum"] == _INT_MIN:
        return
    candidate = _int32(candidate)
    row["raw_minimum"] = (
        row["raw_maximum"] if row["raw_maximum"] < candidate else candidate
    )
    row.update(_effective_bounds(row))
    if row["raw_current"] < row["minimum"]:
        row["raw_current"] = row["minimum"]


def _set_raw_maximum(row, candidate):
    if row["raw_maximum"] == _INT_MAX:
        return
    candidate = _int32(candidate)
    row["raw_maximum"] = (
        row["raw_minimum"] if candidate <= row["raw_minimum"] else candidate
    )
    row.update(_effective_bounds(row))
    # HP has ffw.fZB=true, so lowering its maximum does not clamp the raw
    # current here.  The subsequent eWO current operation uses aYS() to read
    # the visible/clamped current and PA.on() to write the adjusted value.


def _set_hp_current(row, candidate):
    # PA.oo/PA.nG use Java int arithmetic before passing the value through
    # on(); the on() setter then clamps to effective minimum and hard maximum.
    row["raw_current"] = _clamp(_int32(candidate), row["minimum"], row["hard_maximum"])


def apply(state, operation):
    """Apply one qualified native HP eWO root and return its inverse receipt."""
    row = _validated_state(state)
    if (
        not isinstance(operation, dict)
        or operation.get("family") != "eWO"
        or operation.get("stat") != 1
    ):
        raise ValueError("Unsupported native HP operation")
    if operation.get("chance", 100) != 100:
        raise ValueError("Unresolved native HP application chance")
    amount = operation.get("amount")
    reduce_current = operation.get("reduce_current")
    restore_current = operation.get("restore_current")
    if (
        type(amount) is not int
        or amount < 0
        or amount > _INT_MAX
        or type(reduce_current) is not bool
        or type(restore_current) is not bool
    ):
        raise ValueError("Invalid native HP eWO descriptor")
    before = deepcopy(row)
    current_before_bounds = _visible_current(row)
    # eWO.c skips both bound mutations when effective maximum is INT_MAX.
    if row["maximum"] != _INT_MAX:
        _set_raw_minimum(row, row["raw_minimum"] - amount)
        _set_raw_maximum(row, row["raw_maximum"] - amount)
    if reduce_current:
        # eWO.fNL compares the visible PA current before and after its bound
        # changes, then applies `amount - before + after` via PA.oo. This
        # retains over-max raw HP (notably an unwounded/full character) while
        # reducing the visible current by the selected amount.
        current_after_bounds = _visible_current(row)
        change = _int32(_int32(amount - current_before_bounds) + current_after_bounds)
        _set_hp_current(row, row["raw_current"] - change)
    receipt = dict(
        family="eWO",
        stat=1,
        amount=amount,
        restore_current=restore_current,
        reduce_current=reduce_current,
        before=before,
        after=deepcopy(row),
    )
    return row, receipt


def remove(state, receipt):
    """Remove a previously applied HP eWO operation from current actor state."""
    row = _validated_state(state)
    if (
        not isinstance(receipt, dict)
        or receipt.get("family") != "eWO"
        or receipt.get("stat") != 1
    ):
        raise ValueError("Missing native HP eWO receipt")
    amount = receipt.get("amount")
    restore_current = receipt.get("restore_current")
    if type(amount) is not int or amount < 0 or type(restore_current) is not bool:
        raise ValueError("Invalid native HP eWO receipt")
    _set_raw_maximum(row, row["raw_maximum"] + amount)
    _set_raw_minimum(row, row["raw_minimum"] + amount)
    if restore_current:
        available = row["maximum"] - _visible_current(row)
        if amount > available:
            _set_hp_current(row, row["maximum"])
        else:
            _set_hp_current(row, _int32(row["raw_current"] + amount))
    return row
