"""Native aptitude protobuf and level/category budgets from installed bdata."""
from wakfu_server import native_catalog as protocol_catalog
import json
from .paths import DATA_ROOT
from .wire import proto_fields

CATALOG = protocol_catalog.load(DATA_ROOT / "aptitude-rules.json")
BONUSES = {row["id"]: row for row in CATALOG["bonuses"]}
CATEGORIES = {row["id"]: row for row in CATALOG["categories"]}
BONUS_CATEGORY = {
    bonus: row["id"] for row in CATEGORIES.values() for bonus in row["bonuses"]
}


def budgets(level):
    if type(level) is not int or not 1 <= level <= 250:
        raise ValueError("Invalid aptitude level")
    # eQH.dF counts native grant thresholds <= sheet effective level.
    return {
        category: sum(threshold <= level for threshold in row["grant_levels"])
        for category, row in CATEGORIES.items()
    }


def validate(character, blob):
    if not isinstance(blob, bytes) or len(blob) > 65536:
        raise ValueError("Invalid aptitude sheet")
    allocations = {}
    sheet_level = None
    for tag, value in proto_fields(blob):
        if tag == 24:
            if sheet_level is not None or not isinstance(value, int):
                raise ValueError("Invalid aptitude sheet level")
            signed = (value & 0xFFFFFFFF) - (1 << 32) if value & (1 << 31) else value
            if signed not in (-1, character["level"]):
                raise ValueError("Invalid aptitude sheet level")
            sheet_level = signed
        elif tag == 34 and isinstance(value, bytes):
            fields = list(proto_fields(value))
            data = dict(fields)
            if (
                len(fields) != 2
                or set(data) != {8, 16}
                or any(type(v) is not int for v in data.values())
            ):
                raise ValueError("Invalid aptitude allocation")
            bonus, points = data[8], data[16]
            if (
                bonus not in BONUSES
                or bonus not in BONUS_CATEGORY
                or bonus in allocations
            ):
                raise ValueError("Unknown or duplicate aptitude bonus")
            if not 0 <= points <= 32767:
                raise ValueError("Invalid aptitude points")
            maximum = BONUSES[bonus]["maximum"]
            if maximum and points > maximum:
                raise ValueError("Aptitude bonus exceeds its native maximum")
            allocations[bonus] = points
        else:
            raise ValueError("Invalid aptitude protobuf field")
    if sheet_level is None:
        raise ValueError("Missing aptitude sheet level")
    available = budgets(character["level"] if sheet_level == -1 else sheet_level)
    spent = {category: 0 for category in CATEGORIES}
    for bonus, points in allocations.items():
        spent[BONUS_CATEGORY[bonus]] += points
    if any(spent[category] > available[category] for category in spent):
        raise ValueError("Aptitude category exceeds native level budget")
    return dict(
        sheet_level=sheet_level,
        allocations=allocations,
        spent=spent,
        available=available,
    )


EFFECTS = {
    row["bonus"]: row
    for row in protocol_catalog.load(DATA_ROOT / "aptitude-effects.json")
}


def validate_owned_sheet(character, blob, *, build_index=None):
    """Validate against the selected build cap, as the build-save boundary does."""
    index = (
        character.get("active_build_index", 0) if build_index is None else build_index
    )
    saved = character.get("builds", {}).get(index, {})
    if "sheet" in saved:
        from wakfu_server.builds import effective_sheet_level

        level = effective_sheet_level(character, index)
        character = dict(character, level=level, effective_level=level)
    return validate(character, blob)


def bonuses(character, *, build_index=None):
    index = (
        character.get("active_build_index", 0) if build_index is None else build_index
    )
    saved = character.get("builds", {}).get(index, {})
    blob = bytes.fromhex(saved.get("aptitudes", ""))
    if not blob:
        return dict(stats={}, percentages={}, unsupported=[])
    parsed = validate_owned_sheet(character, blob, build_index=index)
    stats = {}
    percentages = {}
    unsupported = []
    native_effects = []
    for bonus, points in parsed["allocations"].items():
        if not points:
            continue
        effect = EFFECTS[bonus]
        values = effect["values_by_points"][points - 1]
        if bonus in (17, 27, 36):
            # These native eQr groups belong to combat initialization, not
            # the flat characteristic reducer. Preserve points and identity.
            native_effects.append(
                dict(bonus=bonus, points=points, effect=effect["effect"])
            )
            continue
        safe = not (effect["criteria"] or effect["triggers"] or effect["target_mask"])
        if (
            safe
            and effect["runner"] == "eWN"
            and len(values) == 3
            and values[1:] == [1, 0]
        ):
            stat = effect["stat_id"]
            stats[stat] = stats.get(stat, 0) + values[0]
        elif safe and effect["runner"] == "eWQ" and len(values) == 1:
            stat = effect["stat_id"]
            stats[stat] = stats.get(stat, 0) + values[0]
        elif safe and bonus == 1 and effect["runner"] == "eZI" and values[1:] == [1, 0]:
            # eVi's generic986 is an eZI(ffw.sgC). eZI→fff.om adds
            # percentage modifier; fff.aYU applies it to the flat maximum.
            percentages[1] = percentages.get(1, 0) + values[0]
        elif (
            safe
            and effect["runner"] == "eYg"
            and effect.get("generic") == 330
            and values == [0]
        ):
            # Native eYg's one-parameter unlimited ordered group evaluates all
            # children at the owned aptitude points. Resolve atomically: a
            # conditional or unsupported child must not produce partial stats.
            children = effect.get("children", [])
            additions = {}
            supported = bool(children)
            for child in children:
                child_values = child.get("values_by_points", [])
                if (
                    child.get("criteria") is not False
                    or child.get("triggers") is not False
                    or type(child.get("target_mask")) is not int
                    or child["target_mask"] != 0
                    or not isinstance(child_values, list)
                    or len(child_values) < points
                    or not isinstance(child_values[points - 1], list)
                    or any(type(value) is not int for value in child_values[points - 1])
                ):
                    supported = False
                    break
                child_values = child_values[points - 1]
                stat = child.get("stat_id")
                if (
                    child.get("runner") == "eWN"
                    and len(child_values) == 3
                    and child_values[1:] == [1, 0]
                ):
                    amount = child_values[0]
                elif child.get("runner") == "eWQ" and len(child_values) == 1:
                    amount = child_values[0]
                elif (
                    child.get("runner") == "eWQ"
                    and child.get("generic") == 39
                    and len(child_values) == 3
                    and child_values[1] == 0
                ):
                    # Native generic39 selects its characteristic from param2.
                    stat, amount = child_values[2], child_values[0]
                else:
                    supported = False
                    break
                if type(stat) is not int or stat <= 0:
                    supported = False
                    break
                additions[stat] = additions.get(stat, 0) + amount
            if supported:
                for stat, delta in additions.items():
                    stats[stat] = stats.get(stat, 0) + delta
            else:
                unsupported.append(
                    dict(bonus=bonus, effect=effect["effect"], runner=effect["runner"])
                )
        else:
            unsupported.append(
                dict(bonus=bonus, effect=effect["effect"], runner=effect["runner"])
            )
    result = dict(stats=stats, percentages=percentages, unsupported=unsupported)
    if native_effects:
        result["native_effects"] = native_effects
    return result
