"""Actual faW/fbd HP PA mutable state, separate from constructor receipts."""
from .combat_casting_range import int32
from .combat_maximum_resource import effective_maximum

SOURCE = "faW_fbd.eRF.sgC.fff.fZB.PA.v1"


def area_hp_pa(row, base, current, contract):
    if contract not in ("faW", "fbd"):
        raise ValueError("Missing native area HP PA constructor authority")
    minimum, maximum = base["minimum"], base["maximum"]
    overlay = row.get("native_area_hp_pa")
    if overlay is None:
        if type(current) is not int or not minimum <= current <= maximum:
            raise ValueError("Missing native area HP initial PA current")
        return dict(
            producer=SOURCE,
            source=contract + ".PA.sgC.aYS",
            contract=contract,
            constructor=dict(base),
            raw_current=current,
            raw_maximum=maximum,
            raw_minimum=minimum,
            percentage=0,
            frozen=False,
            current=current,
            maximum=maximum,
            minimum=minimum,
        )
    if (
        not isinstance(overlay, dict)
        or overlay.get("producer") != SOURCE
        or overlay.get("source") != contract + ".PA.sgC.aYS"
        or overlay.get("contract") != contract
        or overlay.get("constructor") != base
        or type(overlay.get("frozen")) is not bool
    ):
        raise ValueError("Missing native area HP mutable PA authority")
    for key in ("raw_current", "raw_maximum", "raw_minimum", "percentage"):
        if type(overlay.get(key)) is not int or not -(1 << 31) <= overlay[key] < (
            1 << 31
        ):
            raise ValueError("Invalid native area HP PA integer")
    raw, raw_min = overlay["raw_maximum"], overlay["raw_minimum"]
    low, high = base["absolute_minimum"], base["absolute_maximum"]
    maximum = effective_maximum(raw, overlay["percentage"], low, high)
    minimum = max(low, min(high, raw_min))
    effective = max(minimum, min(maximum, overlay["raw_current"]))
    if (
        raw < raw_min
        or maximum < minimum
        or current != effective
        or not minimum <= overlay["raw_current"] <= high
        or any(
            overlay.get(k) != v
            for k, v in (
                ("current", effective),
                ("maximum", maximum),
                ("minimum", minimum),
            )
        )
    ):
        raise ValueError("Native area current HP raw/effective PA mismatch")
    return dict(overlay)


def _persist(row, state, current_key):
    low = state["constructor"]["absolute_minimum"]
    high = state["constructor"]["absolute_maximum"]
    state["minimum"] = max(low, min(high, state["raw_minimum"]))
    state["maximum"] = effective_maximum(
        state["raw_maximum"], state["percentage"], low, high
    )
    state["current"] = max(
        state["minimum"], min(state["maximum"], state["raw_current"])
    )
    row["native_area_hp_pa"] = state
    row[current_key] = state["current"]
    return state


def set_area_hp_maximum(row, state, requested, current_key):
    state = dict(state)
    state["raw_maximum"] = max(state["raw_minimum"], int32(requested))
    return _persist(row, state, current_key)


def set_area_hp_current(row, state, requested, current_key):
    state = dict(state)
    if not state["frozen"]:
        high = state["constructor"]["absolute_maximum"]
        state["raw_current"] = max(state["minimum"], min(high, int32(requested)))
    return _persist(row, state, current_key)


def shift_area_hp_current(row, state, amount, current_key, *, subtract=False):
    if state["frozen"]:
        return _persist(row, dict(state), current_key)
    requested = (
        (
            state["minimum"]
            if amount > state["current"] - state["minimum"]
            else int32(state["raw_current"] - amount)
        )
        if subtract
        else (
            state["maximum"]
            if amount > state["maximum"] - state["current"]
            else int32(state["raw_current"] + amount)
        )
    )
    return set_area_hp_current(row, state, requested, current_key)
