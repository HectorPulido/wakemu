"""Reviewed dungeon stage difficulty using only each monster's native levels.

This is an explicit Wakemu policy, not recovered official room-grade data.
Legacy instance policies remain unchanged; optional encounters are independent.
"""
from copy import deepcopy
from fractions import Fraction
from functools import lru_cache

MODE = "native_stage_progression"
OPTIONAL_MODES = ("native_minimum", "native_maximum")


def prepare_policy(policy, *, provenance):
    if policy is None:
        return dict(mode="native_minimum", provenance=provenance)
    if not isinstance(policy, dict) or policy.get("mode") not in (
        "native_minimum",
        MODE,
    ):
        raise ValueError("Unsupported explicit dungeon grade policy")
    if (
        not isinstance(policy.get("provenance"), str)
        or not policy["provenance"].strip()
    ):
        raise ValueError("Dungeon grade policy requires explicit provenance")
    expected = {"mode", "provenance"}
    if policy["mode"] == MODE:
        expected.add("optional_mode")
        if policy.get("optional_mode") not in OPTIONAL_MODES:
            raise ValueError("Optional dungeon grade policy is absent or unsupported")
    if set(policy) != expected:
        raise ValueError("Unexpected explicit dungeon grade policy fields")
    return deepcopy(policy)


def _room_options(specification, desired, *, endpoint=None):
    candidates = {Fraction(0), Fraction(1), desired}
    for reference, quantity, minimum, maximum in specification:
        width = maximum - minimum
        if width:
            candidates.update(Fraction(k, width) for k in range(width + 1))
    if endpoint is not None:
        candidates = {endpoint}
    count = sum(row[1] for row in specification)
    distinct = {}
    for value in candidates:
        levels = tuple(
            low + (high - low) * value.numerator // value.denominator
            for _, _, low, high in specification
        )
        total = sum(row[1] * level for row, level in zip(specification, levels))
        option = (value, total, count)
        prior = distinct.get(levels)
        if prior is None or (abs(value - desired), value) < (
            abs(prior[0] - desired),
            prior[0],
        ):
            distinct[levels] = option
    return tuple(sorted(distinct.values()))


@lru_cache(maxsize=512)
def path_plan(specifications):
    """Choose the closest native-bounded increasing logical encounter path.

    Equal fractions give each species a nondecreasing native level. Weighted
    means also have to increase, since changing species can otherwise reverse
    difficulty despite an increasing fraction. Fixed native grades may permit
    only equality; impossible paths require roster review rather than buffs.
    """
    count = len(specifications)
    if count == 1:
        return (Fraction(0),), False
    desired = tuple(Fraction(i, count - 1) for i in range(count))
    options = tuple(
        _room_options(
            spec, desired[i], endpoint=desired[i] if i in (0, count - 1) else None
        )
        for i, spec in enumerate(specifications)
    )
    for strict in (True, False):
        states = {0: (Fraction(0), (options[0][0][0],))}
        for stage in range(1, count):
            following = {}
            for index, current in enumerate(options[stage]):
                value, total, size = current
                choices = []
                for old_index, (cost, path) in states.items():
                    previous, old_total, old_size = options[stage - 1][old_index]
                    left, right = old_total * size, total * old_size
                    if value >= previous and (
                        left < right if strict else left <= right
                    ):
                        choices.append(
                            (cost + (value - desired[stage]) ** 2, path + (value,))
                        )
                if choices:
                    following[index] = min(choices)
            states = following
            if not states:
                break
        if states:
            return min(states.values())[1], strict
    raise ValueError(
        "Native dungeon grade ranges cannot form a nondecreasing main path; review room composition"
    )


def stage_plan(config):
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    main = main_room_orders(config["topology"])
    rooms = {r["order"]: r for r in config["compiled_plan"]["rooms"]}
    specifications = tuple(
        tuple(
            sorted(
                (m["ref_id"], m["count"], m["native_min_level"], m["native_max_level"])
                for m in rooms[order]["monsters"]
            )
        )
        for order in main
    )
    return main, path_plan(specifications)


def fraction(config, room_order):
    """Return the fraction of the selected logical main encounter path."""
    from wakfu_server.dungeon_optional_rooms import main_room_orders

    topology = config["topology"]
    main = main_room_orders(topology)
    if type(room_order) is not int:
        raise ValueError("Stage progression requires an explicit integral room")
    if room_order in main:
        # Reviewed branches contain logical stage variants, not extra stages.
        branches = topology.get("branch_routes", ())
        if branches:
            selected = topology.get("selected_branch")
            if selected is not None:
                matches = [b for b in branches if b["key"] == selected]
                if len(matches) != 1:
                    raise ValueError("Unknown selected dungeon level path")
                path = tuple(
                    r["order"] for r in matches[0]["rooms"] if r["order"] in main
                )
                if path != main:
                    raise ValueError(
                        "Selected dungeon level path contradicts logical stages"
                    )
        _, (values, strict) = stage_plan(config)
        value = values[main.index(room_order)]
        return value.numerator, value.denominator
    if room_order not in {r["order"] for r in topology["rooms"]}:
        raise ValueError("Stage progression room is absent")
    # Optional access never adds to the main path denominator or advances it.
    return (1 if config["level_policy"]["optional_mode"] == "native_maximum" else 0), 1


def selector(config, *, room_order=None):
    policy = config["level_policy"]
    if policy.get("mode") != "native_minimum":
        policy = prepare_policy(policy, provenance=config.get("provenance", ""))
    numerator, denominator = (
        (0, 1) if policy["mode"] == "native_minimum" else fraction(config, room_order)
    )

    def select(native, roster):
        minimum, maximum = native["min_level"], native["max_level"]
        if (
            type(minimum) is not int
            or type(maximum) is not int
            or not 1 <= minimum <= maximum <= 32767
            or (minimum, maximum) != (roster["min_level"], roster["max_level"])
        ):
            raise ValueError("Native monster grade bounds changed")
        # Native statistics accepts integral levels throughout this interval.
        # Integer interpolation adds no invented level or characteristic buff.
        return minimum + ((maximum - minimum) * numerator // denominator)

    return select
