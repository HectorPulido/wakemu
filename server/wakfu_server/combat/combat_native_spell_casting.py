"""Installed spell casting tables, separate from the 722 class spell inventory."""
from wakfu_server import native_catalog as protocol_catalog
import os
import json
from functools import lru_cache
from collections import OrderedDict, namedtuple
from threading import RLock
from sys import getsizeof
from wakfu_server.paths import DATA_ROOT
from .combat_conditions import UnknownCondition, evaluate_condition
from .combat_casting_range import int32


@lru_cache(maxsize=1)
def catalog():
    from wakfu_server.combat_published_catalogs import compilation_mode
    from wakfu_server.native_catalog_document import load_published_document

    if not compilation_mode():
        return load_published_document("native-spell-casting.json")["spells"]

    return protocol_catalog.load(DATA_ROOT / "native-spell-casting.json")["spells"]


def native_casting_table(reference, level, *, casting=None, zero_casting=None):
    """Select an explicit native table/index; zero never indexes positive levels."""
    if type(level) is not int or level < 0:
        raise ValueError("Native temporary spell level unavailable")
    if level == 0:
        if zero_casting is None:
            from .combat_class_initialization import level_zero_catalog

            zero_casting = level_zero_catalog().get("casting", {})
        record = zero_casting.get(str(reference))
        index = 0
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("levels"), list)
            or len(record["levels"]) != 1
        ):
            raise ValueError("Native explicit zero spell table unavailable")
    else:
        record = (catalog() if casting is None else casting).get(str(reference))
        index = level - 1
        if (
            not isinstance(record, dict)
            or not isinstance(record.get("levels"), list)
            or index >= len(record["levels"])
        ):
            raise ValueError("Native temporary spell level unavailable")
    return record, index


_SelectedCastingProjection = namedtuple(
    "SelectedCastingProjection",
    "index baseline rules categories roots forbid_QI_P cast_criterion_raw "
    "cast_criterion_native_present cost_categories",
    defaults=(None,),
)
_SELECTED_PROJECTIONS = OrderedDict()
_SELECTED_LOCK = RLock()
_SELECTED_BYTES = 0
_SELECTED_MAX_ENTRIES = 512
_SELECTED_MAX_BYTES = 4 * 1024 * 1024
_CASTING_FLAGS = (
    "line_of_sight",
    "linear",
    "free_cell",
    "range_modifiable",
    "path_option",
    "diagonal",
    "linear_path",
    "allow_self",
)


def _projection(record, index):
    baseline = (
        tuple(record["costs"][index])
        + tuple(record["levels"][index][:2])
        + tuple(record[field] for field in _CASTING_FLAGS)
    )
    rules = tuple(
        (
            rule["criteria"],
            tuple(rule["levels"][index])
            + tuple(rule["ranges"][index])
            + tuple(rule[field] for field in _CASTING_FLAGS),
        )
        for rule in record["conditional"]
    )
    return _SelectedCastingProjection(
        index,
        baseline,
        rules,
        frozenset(record["categories"]),
        tuple(record["levels"][index][2]),
        record["forbid_QI_P"],
        record.get("cast_criterion_raw"),
        record["cast_criterion_native_present"],
        tuple(record["categories"]),
    )


def _immutable_size(value, seen):
    """Charge retained objects; malformed mutable values never enter the cache."""
    identity = id(value)
    if identity in seen:
        return 0
    seen.add(identity)
    if type(value) in (str, bytes, int, float, bool, type(None)):
        return getsizeof(value)
    if isinstance(value, tuple) or type(value) is frozenset:
        return getsizeof(value) + sum(_immutable_size(item, seen) for item in value)
    raise TypeError("Mutable native casting projection")


def _selected_casting_input(reference, level, *, casting=None):
    """Retain only one selected level under its verified publication identity.

    Plain/zero tables remain uncached. The budget charges retained key/projection
    objects plus a conservative serialized source-row charge; the row itself is
    released after construction, and this bound is not a process RSS estimate.
    """
    global _SELECTED_BYTES
    from .combat_published_catalogs import static_catalog_descriptor

    if type(level) is not int or level < 0:
        # Keep the public table's original validation/error contract.
        native_casting_table(reference, level)
    source = None if level == 0 else (catalog() if casting is None else casting)
    descriptor = None if source is None else static_catalog_descriptor(source)
    if (
        descriptor is None
        or descriptor["revision"] == "0" * 64
        or source.representation != "native_json"
    ):
        record, index = native_casting_table(reference, level, casting=source)
        return record, index
    key = (descriptor["revision"], descriptor["collection"], str(reference), level)
    with _SELECTED_LOCK:
        found = _SELECTED_PROJECTIONS.get(key)
        if found is not None:
            _SELECTED_PROJECTIONS.move_to_end(key)
            return found[0]
    record, index = native_casting_table(reference, level, casting=source)
    try:
        projection = _projection(record, index)
    except (KeyError, IndexError, TypeError, ValueError):
        # Preserve legacy error/evaluation order for malformed source metadata.
        # The real record is used only in this call and is never cached.
        return record, index
    try:
        charge = _immutable_size((key, projection), set()) + len(
            json.dumps(record, separators=(",", ":"), ensure_ascii=False).encode(
                "utf-8"
            )
        )
    except (TypeError, ValueError, OverflowError):
        return projection
    if charge > _SELECTED_MAX_BYTES:
        return projection
    with _SELECTED_LOCK:
        found = _SELECTED_PROJECTIONS.get(key)
        if found is not None:
            _SELECTED_PROJECTIONS.move_to_end(key)
            return found[0]
        _SELECTED_PROJECTIONS[key] = (projection, charge)
        _SELECTED_BYTES += charge
        while (
            len(_SELECTED_PROJECTIONS) > _SELECTED_MAX_ENTRIES
            or _SELECTED_BYTES > _SELECTED_MAX_BYTES
        ):
            _, (_, removed) = _SELECTED_PROJECTIONS.popitem(last=False)
            _SELECTED_BYTES -= removed
    return projection


def selected_casting_projection(reference, level, *, casting=None):
    """Return the static selected level, without caching plain/zero tables."""
    selected = _selected_casting_input(reference, level, casting=casting)
    if isinstance(selected, _SelectedCastingProjection):
        return selected
    return _projection(*selected)


def _clear_selected_projections():
    global _SELECTED_BYTES
    with _SELECTED_LOCK:
        _SELECTED_PROJECTIONS.clear()
        _SELECTED_BYTES = 0


def _selected_projection_info():
    with _SELECTED_LOCK:
        return dict(
            entries=len(_SELECTED_PROJECTIONS),
            charged_bytes=_SELECTED_BYTES,
            max_entries=_SELECTED_MAX_ENTRIES,
            max_bytes=_SELECTED_MAX_BYTES,
        )


selected_casting_projection.cache_clear = _clear_selected_projections
selected_casting_projection.cache_info = _selected_projection_info


def definition(reference, level, context, modifiers, *, calculate_costs=True):
    """Select the entire native fyP, preserving ambiguous branches as errors."""
    selected_input = _selected_casting_input(reference, level)
    projection = (
        selected_input
        if isinstance(selected_input, _SelectedCastingProjection)
        else None
    )
    if projection is None:
        record, index = selected_input
        baseline = (
            tuple(record["costs"][index])
            + tuple(record["levels"][index][:2])
            + tuple(record[field] for field in _CASTING_FLAGS)
        )
    else:
        index, baseline = projection.index, projection.baseline
    matches = set()
    matched_rules = []
    unknown_equivalent_rules = []
    evaluated_rules = []
    unknown = False

    def selection_metadata(selected=None):
        return dict(
            reference=reference,
            evaluation_level=level,
            table_index=index,
            selected_origin="unknown"
            if selected is None
            else "conditional"
            if matched_rules
            else "baseline",
            matched_rules=matched_rules,
            evaluated_rules=evaluated_rules,
            unknown_equivalent_rule_indices=unknown_equivalent_rules,
            baseline_values=baseline,
            selected_values=selected,
            unique_matching_rule=len(matched_rules) == 1
            and not unknown_equivalent_rules,
        )

    rules = projection.rules if projection is not None else record["conditional"]
    for rule_index, rule in enumerate(rules):
        if projection is not None:
            criterion, selected = rule
        else:
            selected = (
                tuple(rule["levels"][index])
                + tuple(rule["ranges"][index])
                + tuple(rule[field] for field in _CASTING_FLAGS)
            )
            criterion = rule["criteria"]
        try:
            matched = evaluate_condition(criterion, context)
        except UnknownCondition as error:
            if selected != baseline:
                evaluated_rules.append(
                    dict(index=rule_index, criterion=criterion, result="unknown")
                )
                error.native_casting_selection = selection_metadata()
                raise
            unknown = True
            unknown_equivalent_rules.append(rule_index)
            evaluated_rules.append(
                dict(
                    index=rule_index,
                    criterion=criterion,
                    result="unknown_equivalent",
                )
            )
            continue
        evaluated_rules.append(
            dict(
                index=rule_index,
                criterion=criterion,
                result="matched" if matched else "not_matched",
            )
        )
        if matched:
            matches.add(selected)
            matched_rules.append(dict(index=rule_index, criteria=criterion))
    if len(matches) > 1 or unknown and any(value != baseline for value in matches):
        error = UnknownCondition("Ambiguous native temporary spell table")
        error.native_casting_selection = selection_metadata()
        raise error
    selected = next(iter(matches)) if matches else baseline
    categories = set(
        projection.categories if projection is not None else record["categories"]
    )
    if (
        calculate_costs
        and categories
        and (
            not isinstance(modifiers, dict)
            or any(
                type(key) is not int or type(value) is not int
                for key, value in modifiers.items()
            )
        )
    ):
        raise UnknownCondition("Missing complete native eHl AP modifier snapshot")
    costs = None
    if calculate_costs:
        adjustment = (
            int32(sum(modifiers.get(category, 0) for category in categories))
            if categories
            else 0
        )
        costs = dict(
            ap=max(0, int32(selected[0] + adjustment)),
            mp=max(0, selected[1]),
            wp=max(0, selected[2]),
            conditional_rules=0,
        )
        from .combat_spell_resource_costs import resolve as resolve_full_costs

        full_costs = resolve_full_costs(
            reference, level, context, selection=selection_metadata(selected)
        )
        if tuple(full_costs.get(stat, 0) for stat in (2, 3, 4)) != selected[:3]:
            raise UnknownCondition(
                "Native full resource costs disagree with casting table"
            )
        costs["extra_resource_values"] = {
            stat: value for stat, value in full_costs.items() if stat not in (2, 3, 4)
        }
    return dict(
        native_casting_selection=selection_metadata(selected),
        costs=costs,
        minimum=selected[3],
        maximum=selected[4],
        line_of_sight=selected[5],
        linear=selected[6],
        free_cell=selected[7],
        range_modifiable=selected[8],
        path_option=selected[9],
        diagonal=selected[10],
        linear_path=selected[11],
        allow_self=selected[12],
        forbid_QI_P=(
            projection.forbid_QI_P if projection is not None else record["forbid_QI_P"]
        ),
        cast_criterion_raw=(
            projection.cast_criterion_raw
            if projection is not None
            else record.get("cast_criterion_raw")
        ),
        cast_criterion_native_present=(
            projection.cast_criterion_native_present
            if projection is not None
            else record["cast_criterion_native_present"]
        ),
        categories=tuple(sorted(categories)),
        roots=(
            projection.roots
            if projection is not None
            else tuple(record["levels"][index][2])
        ),
    )


@lru_cache(maxsize=1)
def granted_effect_catalog():
    return protocol_catalog.load(DATA_ROOT / "granted-spell-effect-trees.json")


@lru_cache(maxsize=1)
def merged_spell_effects():
    from wakfu_server.spell_audit import catalog as class_catalog
    from .combat_effect_runtime import _merge_effects

    from .combat_captured_dependencies import merge_captured_effects

    from .combat_triggered_dependencies import merge_effects as merge_triggered_effects

    from .combat_morph_dependencies import merge_effects as merge_morph_effects

    base = merge_morph_effects(
        merge_triggered_effects(merge_captured_effects(class_catalog()["effects"]))
    )
    dependencies = granted_effect_catalog()
    # Definitions do not admit an action. The owned resolver requires its
    # actual native grant UID, level and controller on every cast, independent
    # of the retired feature flag. Keep every original granted dependency
    # available to that same already-authorized execution path.
    return _merge_effects(base, dependencies)


def class_grant_dependency_effects(dependencies):
    metadata = protocol_catalog.load(
        DATA_ROOT / "native-class-spell-grant-closure.json"
    )
    references = metadata.get("effect_reference_closure")
    if (
        metadata.get("schema") != "native-class-spell-grant-closure-v1"
        or not isinstance(references, list)
        or any(type(reference) is not int or reference <= 0 for reference in references)
        or len(references) != len(set(references))
    ):
        raise ValueError("Invalid scoped native class spell grant dependency closure")
    effects = dependencies["effects"]
    return {
        "effects": {
            str(reference): effects[str(reference)]
            for reference in references
            if str(reference) in effects
        }
    }


def class_summon_dependency_effects(dependencies):
    metadata = protocol_catalog.load(
        DATA_ROOT / "native-class-summon-effect-closure.json"
    )
    references = metadata.get("effect_reference_closure")
    if (
        not isinstance(references, list)
        or any(type(reference) is not int or reference <= 0 for reference in references)
        or len(references) != len(set(references))
    ):
        raise ValueError("Invalid scoped native class summon dependency closure")
    effects = dependencies["effects"]
    added = metadata.get("added_effect_ids")
    if (
        not isinstance(added, list)
        or any(type(reference) is not int for reference in added)
        or not set(added) <= set(references)
    ):
        raise ValueError("Invalid scoped native class summon import additions")
    if any(str(reference) not in effects for reference in added):
        raise ValueError("Missing native class summon ability effect definition")
    # Existing granted records can also be actual dependencies of a fresh
    # class summon book. Definitions already supplied by the class/state/area
    # catalogs stay in those catalogs; merge every dependency-catalog member
    # of the exact native closure, regardless of whether this import added it.
    return {
        "effects": {
            str(reference): effects[str(reference)]
            for reference in references
            if str(reference) in effects
        }
    }


def enabled():
    return os.environ.get("WAKFU_NATIVE_GRANTED_CAST", "0") == "1"
