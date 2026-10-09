"""Installed spell casting tables, separate from the 722 class spell inventory."""
from wakfu_server import native_catalog as protocol_catalog
import os
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_conditions import UnknownCondition, evaluate_condition
from .combat_casting_range import int32


@lru_cache(maxsize=1)
def catalog():
    return protocol_catalog.load(DATA_ROOT / "native-spell-casting.json")["spells"]


def definition(reference, level, context, modifiers, *, calculate_costs=True):
    """Select the entire native fyP, preserving ambiguous branches as errors."""
    if type(level) is not int or level < 0:
        raise ValueError("Native temporary spell level unavailable")
    if level == 0:
        from .combat_class_initialization import level_zero_catalog

        record = level_zero_catalog().get("casting", {}).get(str(reference))
        index = 0  # Explicit native zero table, never levels[-1].
    else:
        record = catalog().get(str(reference))
        index = level - 1
    if record is None or index >= len(record["levels"]):
        raise ValueError("Native temporary spell level unavailable")
    baseline = (
        tuple(record["costs"][index])
        + tuple(record["levels"][index][:2])
        + tuple(
            record[field]
            for field in (
                "line_of_sight",
                "linear",
                "free_cell",
                "range_modifiable",
                "path_option",
                "diagonal",
                "linear_path",
                "allow_self",
            )
        )
    )
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

    for rule_index, rule in enumerate(record["conditional"]):
        selected = (
            tuple(rule["levels"][index])
            + tuple(rule["ranges"][index])
            + tuple(
                rule[field]
                for field in (
                    "line_of_sight",
                    "linear",
                    "free_cell",
                    "range_modifiable",
                    "path_option",
                    "diagonal",
                    "linear_path",
                    "allow_self",
                )
            )
        )
        try:
            matched = evaluate_condition(rule["criteria"], context)
        except UnknownCondition as error:
            if selected != baseline:
                evaluated_rules.append(
                    dict(index=rule_index, criterion=rule["criteria"], result="unknown")
                )
                error.native_casting_selection = selection_metadata()
                raise
            unknown = True
            unknown_equivalent_rules.append(rule_index)
            evaluated_rules.append(
                dict(
                    index=rule_index,
                    criterion=rule["criteria"],
                    result="unknown_equivalent",
                )
            )
            continue
        evaluated_rules.append(
            dict(
                index=rule_index,
                criterion=rule["criteria"],
                result="matched" if matched else "not_matched",
            )
        )
        if matched:
            matches.add(selected)
            matched_rules.append(dict(index=rule_index, criteria=rule["criteria"]))
    if len(matches) > 1 or unknown and any(value != baseline for value in matches):
        error = UnknownCondition("Ambiguous native temporary spell table")
        error.native_casting_selection = selection_metadata()
        raise error
    selected = next(iter(matches)) if matches else baseline
    categories = set(record["categories"])
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
        forbid_QI_P=record["forbid_QI_P"],
        cast_criterion_raw=record.get("cast_criterion_raw"),
        cast_criterion_native_present=record["cast_criterion_native_present"],
        categories=tuple(sorted(categories)),
        roots=tuple(record["levels"][index][2]),
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
    if enabled():
        return _merge_effects(base, dependencies)
    # Own-book class summon abilities are ordinary class dependencies, not
    # temporary grants. Keep their scoped definitions independent of the
    # permission gate for granting extra actions to an actor.
    merged = _merge_effects(base, class_summon_dependency_effects(dependencies))
    return _merge_effects(merged, class_grant_dependency_effects(dependencies))


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
