"""Conservative target-distance bounds derived from native casting tables.

This module only produces advisory upper bounds. Missing or unfamiliar native
authority makes the envelope incomplete so consumers must leave candidates in.
"""

from .native_deadline import check


ENVELOPE_VERSION = "native-target-envelope-v1"
ENVELOPE_BASIS = "native-casting-range-upper-bound"
_I32_MIN = -(1 << 31)
_I32_MAX = (1 << 31) - 1

_SPELL_FIELDS = {
    "protected",
    "maximum_level",
    "line_of_sight",
    "linear",
    "free_cell",
    "levels",
    "costs",
    "categories",
    "conditional",
    "range_modifiable",
    "path_option",
    "diagonal",
    "linear_path",
    "allow_self",
    "forbid_QI_P",
    "cast_criterion_raw",
    "cast_criterion_native_present",
}
_CONDITIONAL_FIELDS = {
    "linear",
    "line_of_sight",
    "levels",
    "criteria",
    "ranges",
    "free_cell",
    "range_modifiable",
    "path_option",
    "diagonal",
    "linear_path",
    "allow_self",
}


def _int32(value):
    return type(value) is int and _I32_MIN <= value <= _I32_MAX


def _range_row(record, level, conditional=None):
    if level < 1:
        raise ValueError("Native casting level unavailable")
    index = level - 1
    if conditional is None:
        levels = record["levels"]
        if not isinstance(levels, list) or index >= len(levels):
            raise ValueError("Native casting baseline level unavailable")
        row = levels[index]
        if (
            not isinstance(row, list)
            or len(row) != 3
            or not isinstance(row[2], list)
            or any(type(root) is not int for root in row[2])
        ):
            raise ValueError("Malformed native casting baseline level")
        minimum, maximum = row[:2]
        modifiable = record["range_modifiable"]
    else:
        ranges = conditional["ranges"]
        if not isinstance(ranges, list) or index >= len(ranges):
            raise ValueError("Native conditional range unavailable")
        row = ranges[index]
        if not isinstance(row, list) or len(row) != 2:
            raise ValueError("Malformed native conditional range")
        minimum, maximum = row
        modifiable = conditional["range_modifiable"]
    if not _int32(minimum) or not _int32(maximum) or type(modifiable) is not bool:
        raise ValueError("Invalid native casting range values")
    return {"minimum": minimum, "maximum": maximum, "range_modifiable": modifiable}


def _validate_record(record):
    if not isinstance(record, dict) or set(record) != _SPELL_FIELDS:
        raise ValueError("Unknown or incomplete native casting spell schema")
    if (
        type(record["maximum_level"]) is not int
        or record["maximum_level"] < 0
        or not isinstance(record["costs"], list)
        or type(record["protected"]) is not bool
        or type(record["forbid_QI_P"]) is not bool
        or type(record["cast_criterion_native_present"]) is not bool
        or not isinstance(record["cast_criterion_raw"], str)
    ):
        raise ValueError("Invalid native casting record metadata")
    if (
        not isinstance(record["levels"], list)
        or not isinstance(record["conditional"], list)
        or not isinstance(record["categories"], list)
        or any(type(category) is not int for category in record["categories"])
        or len(record["categories"]) != len(set(record["categories"]))
    ):
        raise ValueError("Invalid native casting record")
    for name in (
        "linear",
        "line_of_sight",
        "free_cell",
        "range_modifiable",
        "path_option",
        "diagonal",
        "linear_path",
        "allow_self",
    ):
        if type(record[name]) is not bool:
            raise ValueError("Invalid native casting flag")
    for row in record["conditional"]:
        if not isinstance(row, dict) or set(row) != _CONDITIONAL_FIELDS:
            raise ValueError("Unknown or incomplete native conditional schema")
        if (
            not isinstance(row["levels"], list)
            or not isinstance(row["ranges"], list)
            or not isinstance(row["criteria"], str)
            or any(
                type(row[field]) is not bool
                for field in (
                    "linear",
                    "line_of_sight",
                    "free_cell",
                    "range_modifiable",
                    "path_option",
                    "diagonal",
                    "linear_path",
                    "allow_self",
                )
            )
        ):
            raise ValueError("Invalid native conditional casting row")
        if len(row["levels"]) <= 0 or len(row["ranges"]) != len(row["levels"]):
            raise ValueError("Incomplete native conditional casting levels")
        for level_row in row["levels"]:
            if (
                not isinstance(level_row, list)
                or len(level_row) != 3
                or any(type(value) is not int for value in level_row)
            ):
                raise ValueError("Malformed native conditional level row")
        for range_row in row["ranges"]:
            if (
                not isinstance(range_row, list)
                or len(range_row) != 2
                or any(not _int32(value) for value in range_row)
            ):
                raise ValueError("Malformed native conditional range row")


def derive_native_target_envelope(
    *,
    actor_id,
    origin,
    owned_spells,
    casting_catalog,
    override_categories,
    resolve_current,
    resolve_range,
):
    """Build a union upper bound, or explicitly fail open.

    `resolve_current(spell, level)` asks the actual native definition selector
    to validate its current conditional state. `resolve_range(spell, level,
    rule, context)` calls the actual native range resolver with the current
    actor and cast context.
    """
    if (
        type(actor_id) is not int
        or not isinstance(origin, (tuple, list))
        or len(origin) != 3
        or any(not _int32(value) for value in origin)
    ):
        raise ValueError("Native target mask needs safe actor coordinates")
    if not isinstance(owned_spells, dict) or not isinstance(casting_catalog, dict):
        raise ValueError("Missing complete native casting catalogue")
    if not isinstance(override_categories, set) or any(
        type(value) is not int for value in override_categories
    ):
        raise ValueError("Missing native normal-casting override metadata")

    result = dict(
        version=ENVELOPE_VERSION,
        actorId=actor_id,
        origin=list(origin),
        metric="xy-manhattan",
        complete=True,
        maximum=0,
        basis=ENVELOPE_BASIS,
        spells=[],
        unrestrictedSpellIds=[],
        unknownSpellIds=[],
    )
    maximum_union = 0
    for spell, level in sorted(owned_spells.items()):
        check()
        row = dict(
            spellId=spell,
            level=level,
            minimum=0,
            maximum=None,
            source="baseline+all-conditional-branches",
        )
        try:
            if (
                type(spell) is not int
                or spell <= 0
                or type(level) is not int
                or level < 1
            ):
                raise ValueError("Invalid owned native spell")
            record = casting_catalog.get(str(spell))
            _validate_record(record)
            index = level - 1
            if (
                level > record["maximum_level"]
                or index >= len(record["levels"])
                or index >= len(record["costs"])
            ):
                raise ValueError("Owned level outside native casting catalogue")
            if set(record["categories"]) & override_categories:
                row["reason"] = "native-normal-casting-override"
                result["unrestrictedSpellIds"].append(spell)
                result["complete"] = False
                result["spells"].append(row)
                continue

            # Validate the active conditional selection with the world selector.
            selected = resolve_current(spell, level)
            if (
                not isinstance(selected, tuple)
                or len(selected) != 2
                or not isinstance(selected[0], dict)
            ):
                raise ValueError("Native conditional selection unavailable")
            selected_rule, cast_context = selected
            if not _int32(selected_rule.get("minimum")) or selected_rule["minimum"] < 0:
                raise ValueError("Signed native range minimum disables XY bound")

            maximum = 0
            branches = [None, *record["conditional"]]
            # Include the exact current native selection as well as every raw
            # catalog branch. This remains an upper bound if selection logic
            # adds a branch-specific adjustment in a future compatible build.
            resolved_selected = resolve_range(spell, level, selected_rule, cast_context)
            selected_maximum = (
                resolved_selected.get("maximum")
                if isinstance(resolved_selected, dict)
                else None
            )
            if not _int32(selected_maximum):
                raise ValueError(
                    "Native range resolver returned invalid selected bound"
                )
            maximum = max(0, selected_maximum)
            for branch in branches:
                check()
                raw = _range_row(record, level, branch)
                if raw["minimum"] < 0:
                    raise ValueError("Signed native range minimum disables XY bound")
                resolved = resolve_range(
                    spell,
                    level,
                    {**raw, "categories": tuple(record["categories"])},
                    cast_context,
                )
                upper = resolved.get("maximum") if isinstance(resolved, dict) else None
                if not _int32(upper):
                    raise ValueError("Native range resolver returned invalid bound")
                # Native self-targeting accepts distance zero even when the
                # table maximum is negative; zero is the conservative floor.
                maximum = max(maximum, upper, 0)
            row["maximum"] = maximum
            result["spells"].append(row)
            maximum_union = max(maximum_union, maximum)
        except TimeoutError:
            raise
        except Exception:
            # Preserve the spell and all raw catalog data. Only the advisory
            # envelope becomes unknown when a branch cannot be proved.
            row["reason"] = "native-range-unknown"
            result["unknownSpellIds"].append(spell)
            result["complete"] = False
            result["spells"].append(row)

    if result["complete"]:
        result["maximum"] = maximum_union
    else:
        result["maximum"] = None
    return result
