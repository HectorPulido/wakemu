"""Native fee/fed portal eligibility over complete Qs and QI authority.

This module evaluates casting geometry; fee is a native class name, not a
resource surcharge. Portal identity choice and cast execution are separate.
"""
from dataclasses import dataclass
from types import MappingProxyType
from .combat_gate_conditions import _gate_distance, _int32


def _cell(value):
    if (
        not isinstance(value, (tuple, list))
        or len(value) != 3
        or any(type(v) is not int for v in value)
        or any(not -(1 << 31) <= v < (1 << 31) for v in value[:2])
        or not -32768 <= value[2] <= 32767
    ):
        raise ValueError("Missing native portal cell")
    return tuple(value)


def portal_exit_distance(source, target):
    """aBn.cG differs from ala.c at Java Math.abs(INT_MIN)."""
    source, target = _cell(source), _cell(target)
    distances = []
    for coordinate, other in zip(source[:2], target[:2]):
        delta = _int32(other - coordinate)
        distances.append(delta if delta == -(1 << 31) else abs(delta))
    return _int32(sum(distances))


def _boolean(callback, *args):
    if not callable(callback):
        raise ValueError("Missing native portal conditional/visibility authority")
    result = callback(*args)
    if type(result) is not bool:
        raise ValueError("Unknown native portal conditional/visibility result")
    return result


@dataclass(frozen=True)
class NativePortalEvaluation:
    entry_uids: frozenset
    exit_failures: object

    @property
    def has_entry(self):
        return bool(self.entry_uids)  # fee.fYt

    @property
    def range_accepts(self):
        return any("twI" not in failures for failures in self.exit_failures.values())

    @property
    def alignment_accepts(self):
        return any(
            not ({"twU", "twI"} & failures) for failures in self.exit_failures.values()
        )

    @property
    def los_accepts(self):
        return any(not failures for failures in self.exit_failures.values())


def evaluate_portal_casting(
    areas,
    *,
    caster_cell,
    caster_affiliation,
    target_cell,
    minimum,
    maximum,
    same_cell_category,
    cell_occupants,
    los_required,
    linear_required,
    visible,
):
    """Reproduce fed.bot and fee.fYt/u/v/w without choosing a HashSet member.

    los_required selects fyF.a with actual null target. linear_required selects
    fyF.b using the supplied native aBn target: gate cell for entry, requested
    target cell for exit. visible is actual fcr with the caster's native height.
    Caller owns conditional selection and geometry producers; no guessed LOS,
    terrain walkability, affiliation or portal owner fallback is permitted.
    """
    caster_cell, target_cell = _cell(caster_cell), _cell(target_cell)
    if (
        not isinstance(areas, (tuple, list))
        or type(caster_affiliation) is not int
        or not -128 <= caster_affiliation <= 127
        or any(
            type(v) is not int or not -(1 << 31) <= v < (1 << 31)
            for v in (minimum, maximum)
        )
        or type(same_cell_category) is not bool
    ):
        raise ValueError("Missing native portal casting context")
    gates = {}
    for row in areas:
        if not isinstance(row, dict) or type(row.get("native_type_id")) is not int:
            raise ValueError("Missing complete native Qs population")
        if row["native_type_id"] != 19:
            continue
        affiliation = row.get("native_fight_affiliation")
        if type(affiliation) is not int or not -128 <= affiliation <= 127:
            raise ValueError("Missing captured native portal affiliation")
        if affiliation != caster_affiliation:
            continue
        uid = row.get("uid")
        if type(uid) is not int or not -(1 << 63) <= uid < (1 << 63) or uid in gates:
            raise ValueError("Missing unique native portal identity")
        cell = _cell(row.get("cell"))
        if not callable(cell_occupants):
            raise ValueError("Missing complete native QI.U authority")
        occupants = cell_occupants(*cell[:2])
        if not isinstance(occupants, frozenset) or any(
            type(v) is not int or not -128 <= v <= 127 for v in occupants
        ):
            raise ValueError("Missing complete native QI.U obstacle identities")
        if not occupants:
            gates[uid] = cell
    entries = set()
    for uid, cell in gates.items():
        distance = _gate_distance(cell, caster_cell)
        if not minimum <= distance <= maximum:
            continue
        if _boolean(los_required) and not _boolean(visible, caster_cell, cell):
            continue
        if _boolean(linear_required, cell) and not (
            cell[0] == caster_cell[0] or cell[1] == caster_cell[1]
        ):
            continue
        entries.add(uid)
    exits = {} if not entries else dict(gates)
    if len(entries) == 1:
        exits.pop(next(iter(entries)), None)
    failures_by_uid = {}
    for uid, cell in exits.items():
        distance = portal_exit_distance(cell, target_cell)
        failures = set()
        if same_cell_category:
            if distance > 0:
                failures.add("twI")
        else:
            if _boolean(linear_required, target_cell) and not (
                target_cell[0] == cell[0] or target_cell[1] == cell[1]
            ):
                failures.add("twU")
            if not minimum <= distance <= maximum:
                failures.add("twI")
            if _boolean(los_required) and not _boolean(visible, cell, target_cell):
                failures.add("twG")
        failures_by_uid[uid] = frozenset(failures)
    return NativePortalEvaluation(frozenset(entries), MappingProxyType(failures_by_uid))
