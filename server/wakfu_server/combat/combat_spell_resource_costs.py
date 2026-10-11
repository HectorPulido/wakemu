"""Complete fyP resource tables; signed resource111 follows fyM/fcN.

The export is a PostgreSQL catalog document. Missing authority is never an
empty cost map. AP/MP/WP retain their public three-key representation.
"""
from functools import lru_cache
import math
import struct

from wakfu_server import native_catalog
from wakfu_server.paths import DATA_ROOT
from .combat_casting_range import int32
from .combat_conditions import UnknownCondition, evaluate_condition


def _float(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


@lru_cache(maxsize=1)
def catalog():
    try:
        document = native_catalog.load(DATA_ROOT / "native-spell-resource-costs.json")
    except FileNotFoundError as error:
        raise UnknownCondition(
            "Missing complete native spell resource-cost authority"
        ) from error
    if document.get("schema") != "native-spell-resource-costs-v1":
        raise UnknownCondition("Missing complete native spell resource-cost authority")
    return document["spells"]


def table_values(table, level):
    result = {}
    for key, values in table["resources"].items():
        stat = int(key)
        if (
            not 0 <= stat <= 255
            or level >= len(values)
            or type(values[level]) is not int
        ):
            raise UnknownCondition("Invalid native full resource-cost table")
        result[stat] = int32(values[level])
    return tuple(sorted(result.items()))


def resolve(reference, level, context, *, records=None, selection=None):
    """Whole-table replacement, including ambiguity in extra resources."""
    record = (catalog() if records is None else records).get(str(reference))
    if (
        record is None
        or type(level) is not int
        or not 0 <= level <= record["maximum_level"]
    ):
        raise UnknownCondition("Missing native full spell resource-cost level")
    baseline = table_values(record["baseline"], level)
    matches, unknown = set(), False
    evaluated = None
    if selection is not None:
        evaluated = selection.get("evaluated_rules")
        if (
            selection.get("reference") != reference
            or selection.get("evaluation_level") != level
            or not isinstance(evaluated, list)
            or len(evaluated) != len(record["conditional"])
        ):
            raise UnknownCondition("Conflicting native full-cost selection authority")
        for index, (result, rule) in enumerate(zip(evaluated, record["conditional"])):
            if (
                result.get("index") != index
                or result.get("criterion") != rule["criteria"]
                or result.get("result")
                not in ("matched", "not_matched", "unknown_equivalent")
            ):
                raise UnknownCondition("Conflicting native full-cost rule selection")
    for index, rule in enumerate(record["conditional"]):
        candidate = table_values(rule, level)
        try:
            if evaluated is None:
                matched = evaluate_condition(rule["criteria"], context)
            elif evaluated[index]["result"] == "unknown_equivalent":
                raise UnknownCondition("Unresolved native full-cost rule")
            else:
                matched = evaluated[index]["result"] == "matched"
        except UnknownCondition:
            if candidate != baseline:
                raise
            unknown = True
            continue
        if matched:
            matches.add(candidate)
    if len(matches) > 1 or unknown and any(value != baseline for value in matches):
        raise UnknownCondition("Ambiguous native full resource-cost table")
    return dict(next(iter(matches)) if matches else baseline)


def hupper_delta(value, characteristics):
    """fyM.a/gF: positive generation113, otherwise consumption112.

    Native multiply wraps before conversion to float; GS.B floors and GS.C
    ceils. Absence is meaningful only in the complete characteristic mapping.
    """
    if type(value) is not int or not isinstance(characteristics, dict):
        raise UnknownCondition("Missing native signed-resource modifier authority")
    stat = 113 if value >= 0 and 113 in characteristics else 112
    modifier = characteristics.get(stat, 0)
    if type(modifier) is not int:
        raise UnknownCondition("Invalid native signed-resource modifier")
    fraction = _float(_float(int32(value * modifier)) / _float(100))
    rounded = math.floor(fraction) if modifier > 0 else math.ceil(fraction)
    return int32(value + rounded)


def extra_costs(values, actor):
    """Produce bounded current deltas; ordinary costs are negative deltas."""
    result = {}
    for stat, value in values.items():
        if stat in (2, 3, 4):
            continue
        # eHl.a only modifies AP and RANGE. No RANGE resource key occurs in
        # the full source export; retain a precise guard if one appears later.
        if stat == 11:
            raise UnknownCondition(
                "Native RANGE resource-cost modifier requires authority"
            )
        result[stat] = (
            hupper_delta(value, actor.effect_stats) if stat == 111 else -max(0, value)
        )
    return result


def validate_extra_resources(actor, deltas):
    from .combat_maximum_resource import _snapshot

    for stat, delta in deltas.items():
        if type(stat) is not int or type(delta) is not int:
            raise UnknownCondition("Invalid native extra-resource payment")
        current, _, _, _, _, _, _, _ = _snapshot(actor, stat)
        if delta < 0 and abs(delta) > current:
            error = ValueError("Insufficient authoritative extra spell resource")
            error.cast_validation_code = "insufficient_resources"
            raise error


def pay_extra_resources(actor, deltas, *, fight=None):
    """Wakemu atomic cast policy: bounded PA current delta, no synthetic Qe.

    This does not pretend resource111 is eWf's fourth resource (which is shk).
    The surrounding spell preview owns rollback and subsequent stat delivery.
    """
    from .combat_maximum_resource import _snapshot, _write

    validate_extra_resources(actor, deltas)
    receipt = []
    for stat, delta in deltas.items():
        current, raw, maximum, minimum, *_ = _snapshot(actor, stat)
        after = (
            current
            if stat in actor.effect_frozen
            else max(minimum, min(maximum, int32(current + delta)))
        )
        from .combat_hupper_resource_binding import set_current

        if stat == 111 and set_current(actor, after):
            pass
        elif getattr(actor, "native_copy_pa_source", None) is not None:
            if fight is None or fight.actors.get(actor.id) is not actor:
                raise UnknownCondition("Missing owned copied PA payment context")
            from .combat_stat_handler import _write as write_current

            write_current(fight, actor.id, actor, stat, after)
        else:
            _write(actor, stat, after, raw, maximum)
        receipt.append(
            dict(stat_id=stat, requested_delta=delta, actual_delta=after - current)
        )
    return tuple(receipt)
