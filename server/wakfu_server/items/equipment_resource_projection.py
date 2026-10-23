"""Pure ordered replay for native equipment AP/MP/WP resource operations.

Rows are full native PA snapshots.  The caller supplies eWN's already
calculated/cap-filtered amount; this module only reproduces the PA mutation
and inverse semantics.  Inverses always operate on the current state, so
removing one equipment effect does not reset changes made by its siblings.
"""

from copy import deepcopy

from wakfu_server.combat_maximum_resource import _int32, effective_maximum

_INT_MIN = -(1 << 31)
_INT_MAX = (1 << 31) - 1
_RESOURCE_STATS = {2, 3, 4}


def _field(row, primary, alternate=None):
    if primary in row:
        return row[primary]
    if alternate is not None and alternate in row:
        return row[alternate]
    raise ValueError(f"Missing native resource field: {primary}")


def _validated_state(state):
    if not isinstance(state, dict):
        raise ValueError("Native resource state must be a mapping")
    row = deepcopy(state)
    current = row.get("current")
    raw_min = _field(row, "raw_minimum", "raw_min")
    raw_max = _field(row, "raw_maximum", "raw_max")
    percentage = row.get("percentage")
    low, high = row.get("hard_minimum"), row.get("hard_maximum")
    values = (current, raw_min, raw_max, percentage, low, high)
    if any(type(value) is not int for value in values):
        raise ValueError("Incomplete native resource snapshot")
    if any(value < _INT_MIN or value > _INT_MAX for value in values):
        raise ValueError("Native resource snapshot exceeds Java int range")
    if low > high or raw_min > raw_max:
        raise ValueError("Invalid native raw resource bounds")
    minimum = max(low, min(high, raw_min))
    maximum = effective_maximum(raw_max, percentage, low, high)
    if current < minimum or current > maximum:
        raise ValueError("Native resource current is outside effective bounds")
    if "minimum" in row and row["minimum"] != minimum:
        raise ValueError("Native effective minimum does not match raw minimum")
    if "maximum" in row and row["maximum"] != maximum:
        raise ValueError("Native effective maximum does not match raw maximum")
    row.update(
        current=current,
        raw_minimum=raw_min,
        raw_maximum=raw_max,
        minimum=minimum,
        maximum=maximum,
    )
    return row


def _clamp_current(row, current):
    row["current"] = max(row["minimum"], min(row["maximum"], current))


def _set_raw_minimum(row, candidate):
    raw_max = row["raw_maximum"]
    if row["raw_minimum"] == _INT_MIN:
        return
    candidate = _int32(candidate)
    row["raw_minimum"] = raw_max if raw_max < candidate else candidate
    row["minimum"] = max(
        row["hard_minimum"], min(row["hard_maximum"], row["raw_minimum"])
    )
    _clamp_current(row, row["current"])


def _set_raw_maximum(row, candidate):
    raw_min = row["raw_minimum"]
    if row["raw_maximum"] == _INT_MAX:
        return
    candidate = _int32(candidate)
    row["raw_maximum"] = raw_min if candidate <= raw_min else candidate
    row["maximum"] = effective_maximum(
        row["raw_maximum"], row["percentage"], row["hard_minimum"], row["hard_maximum"]
    )
    _clamp_current(row, row["current"])


def _kind_descriptor(kind):
    if isinstance(kind, str):
        descriptor = {"family": kind}
    elif isinstance(kind, dict):
        descriptor = dict(kind)
    else:
        raise ValueError("Resource operation kind must be a family or descriptor")
    family = descriptor.get("family", descriptor.get("kind"))
    if family not in ("eWO", "eWN"):
        raise ValueError("Unsupported native equipment resource family")
    descriptor["family"] = family
    return descriptor


def apply_operation(state, amount, kind, *, subtract=False):
    """Apply one native operation; return ``(new_state, inverse_receipt)``.

    eWO takes a positive magnitude and is a reduction (``subtract=True``).
    eWN takes its signed, preprocessed amount.  Its raw maximum change and
    current change are recorded separately because native removal subtracts
    the raw ``actual`` for AP/MP/WP, not the effective-maximum delta.
    """
    if (
        type(amount) is not int
        or amount < _INT_MIN
        or amount > _INT_MAX
        or type(subtract) is not bool
    ):
        raise ValueError("Invalid native resource operation amount")
    row = _validated_state(state)
    descriptor = _kind_descriptor(kind)
    family = descriptor["family"]
    if family == "eWO":
        if amount < 0 or not subtract:
            raise ValueError("eWO requires a positive subtractive magnitude")
        if descriptor.get("stat") not in (None, *_RESOURCE_STATS):
            raise ValueError("Unsupported eWO resource characteristic")
        restore_current = descriptor.get("restore_current", True)
        reduce_current = descriptor.get("reduce_current", True)
        if type(restore_current) is not bool or type(reduce_current) is not bool:
            raise ValueError("Invalid eWO current flags")
        before = deepcopy(row)
        # Native eWO.c skips both PA bound mutations at the effective MAX
        # sentinel, while its optional current reduction still runs.
        if row["maximum"] != _INT_MAX:
            # Native eWO.c: PA.oq(-amount), then PA.op(-amount).
            _set_raw_minimum(row, row["raw_minimum"] - amount)
            _set_raw_maximum(row, row["raw_maximum"] - amount)
        # PA.oo applies the optional current reduction after those mutations.
        after_bounds = row["current"]
        if reduce_current:
            remaining = _int32(amount - _int32(before["current"] - after_bounds))
            _clamp_current(row, _int32(after_bounds - remaining))
        receipt = dict(
            family="eWO",
            amount=amount,
            actual=amount,
            subtract=True,
            restore_current=restore_current,
            reduce_current=reduce_current,
            before=before,
            after=deepcopy(row),
        )
        return row, receipt

    if descriptor.get("stat") not in (None, *_RESOURCE_STATS):
        raise ValueError("Unsupported eWN resource characteristic")
    apply_current = descriptor.get("apply_current", False)
    remove_current = descriptor.get("remove_current", False)
    if type(apply_current) is not bool or type(remove_current) is not bool:
        raise ValueError("Invalid eWN current flags")
    signed_amount = _int32(-amount) if subtract else amount
    before = deepcopy(row)
    raw = row["raw_maximum"]
    updated_raw = (
        raw if raw == _INT_MAX else max(row["raw_minimum"], _int32(raw + signed_amount))
    )
    updated = effective_maximum(
        updated_raw, row["percentage"], row["hard_minimum"], row["hard_maximum"]
    )
    actual = _int32(updated_raw - raw)
    effective_delta = _int32(updated - row["maximum"])
    # Native PA.op clamps current to the new effective maximum before nG.
    _clamp_current(row, row["current"])
    row["raw_maximum"] = updated_raw
    row["maximum"] = updated
    _clamp_current(row, row["current"])
    if apply_current:
        _clamp_current(row, _int32(row["current"] + effective_delta))
    receipt = dict(
        family="eWN",
        amount=signed_amount,
        actual=actual,
        effective_delta=effective_delta,
        apply_current=apply_current,
        remove_current=remove_current,
        before=before,
        after=deepcopy(row),
    )
    return row, receipt


def remove_operation(state, receipt):
    """Remove an applied operation from the supplied *current* state."""
    if not isinstance(receipt, dict):
        raise ValueError("Missing native resource operation receipt")
    row = _validated_state(state)
    family = receipt.get("family")
    if family == "eWO":
        amount = receipt.get("actual")
        restore_current = receipt.get("restore_current")
        if type(amount) is not int or amount < 0 or type(restore_current) is not bool:
            raise ValueError("Invalid eWO removal receipt")
        # Native bbR restores max (PA.op) before minimum (PA.oq).
        _set_raw_maximum(row, row["raw_maximum"] + amount)
        _set_raw_minimum(row, row["raw_minimum"] + amount)
        if restore_current:
            _clamp_current(row, _int32(row["current"] + amount))
        return row
    if family == "eWN":
        actual = receipt.get("actual")
        remove_current = receipt.get("remove_current")
        if type(actual) is not int or type(remove_current) is not bool:
            raise ValueError("Invalid eWN removal receipt")
        raw = row["raw_maximum"]
        updated_raw = (
            raw if raw == _INT_MAX else max(row["raw_minimum"], _int32(raw - actual))
        )
        updated = effective_maximum(
            updated_raw, row["percentage"], row["hard_minimum"], row["hard_maximum"]
        )
        if remove_current:
            # Native eWN.bbR subtracts entry.actual for stats 2/3/4.
            _clamp_current(row, _int32(row["current"] - actual))
        row["raw_maximum"] = updated_raw
        row["maximum"] = updated
        _clamp_current(row, row["current"])
        return row
    raise ValueError("Unsupported native resource removal receipt")


def trace(operations, baseline, kinds):
    """Replay ordered ``(stat, amount, subtract)`` operations over PA rows.

    ``kinds`` maps each stat id to ``"eWO"``/``"eWN"`` or a descriptor.  A
    descriptor may also provide ``stat`` and native current flags.  The trace
    records every intermediate state and supplies receipts suitable for
    removing effects in any caller-selected order against the then-current
    sibling state.
    """
    if not isinstance(baseline, dict) or not isinstance(kinds, dict):
        raise ValueError("Missing native resource baseline or operation kinds")
    state = {stat: _validated_state(row) for stat, row in baseline.items()}
    steps = []
    for index, operation in enumerate(operations):
        if not isinstance(operation, (tuple, list)) or len(operation) != 3:
            raise ValueError("Resource operations must be (stat, amount, subtract)")
        stat, amount, subtract = operation
        if type(stat) is not int or stat not in state:
            raise ValueError("Resource operation references an absent PA snapshot")
        kind = kinds.get(stat)
        if kind is None:
            raise ValueError("Missing native resource operation family")
        descriptor = _kind_descriptor(kind)
        descriptor["stat"] = stat
        before = deepcopy(state[stat])
        after, receipt = apply_operation(
            state[stat], amount, descriptor, subtract=subtract
        )
        state[stat] = after
        steps.append(
            dict(
                index=index,
                stat=stat,
                amount=amount,
                subtract=subtract,
                family=descriptor["family"],
                before=before,
                after=deepcopy(after),
                receipt=receipt,
            )
        )
    return dict(
        initial={stat: _validated_state(row) for stat, row in baseline.items()},
        final=state,
        current={stat: row["current"] for stat, row in state.items()},
        minima={stat: row["minimum"] for stat, row in state.items()},
        maxima={stat: row["maximum"] for stat, row in state.items()},
        raw_minima={stat: row["raw_minimum"] for stat, row in state.items()},
        raw_maxima={stat: row["raw_maximum"] for stat, row in state.items()},
        steps=steps,
        inverses=[step["receipt"] for step in steps],
    )
