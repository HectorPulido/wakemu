"""Installed spell casting tables, separate from the 722 class spell inventory."""
import gzip
import os
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_conditions import UnknownCondition, evaluate_condition


@lru_cache(maxsize=1)
def catalog():
    with gzip.open(DATA_ROOT / "native-spell-casting.json.gz", "rt") as stream:
        return json.load(stream)["spells"]


def definition(reference, level, context, modifiers):
    """Select the entire native fyP, preserving ambiguous branches as errors."""
    record = catalog().get(str(reference))
    if (
        record is None
        or type(level) is not int
        or not 1 <= level <= len(record["levels"])
    ):
        raise ValueError("Native temporary spell level unavailable")
    index = level - 1
    baseline = (
        tuple(record["costs"][index])
        + tuple(record["levels"][index][:2])
        + (record["line_of_sight"], record["linear"], record["free_cell"])
    )
    matches = set()
    unknown = False
    for rule in record["conditional"]:
        selected = (
            tuple(rule["levels"][index])
            + tuple(rule["ranges"][index])
            + (rule["line_of_sight"], rule["linear"], rule["free_cell"])
        )
        try:
            matched = evaluate_condition(rule["criteria"], context)
        except UnknownCondition:
            if selected != baseline:
                raise
            unknown = True
            continue
        if matched:
            matches.add(selected)
    if len(matches) > 1 or unknown and any(value != baseline for value in matches):
        raise UnknownCondition("Ambiguous native temporary spell table")
    selected = next(iter(matches)) if matches else baseline
    categories = set(record["categories"])
    if categories and (
        not isinstance(modifiers, dict)
        or any(
            type(key) is not int or type(value) is not int
            for key, value in modifiers.items()
        )
    ):
        raise UnknownCondition("Missing complete native eHl AP modifier snapshot")
    adjustment = (
        sum(modifiers.get(category, 0) for category in categories) if categories else 0
    )
    costs = dict(
        ap=max(0, selected[0] + adjustment),
        mp=max(0, selected[1]),
        wp=max(0, selected[2]),
        conditional_rules=0,
    )
    return dict(
        costs=costs,
        minimum=selected[3],
        maximum=selected[4],
        line_of_sight=selected[5],
        linear=selected[6],
        free_cell=selected[7],
        roots=tuple(record["levels"][index][2]),
    )


@lru_cache(maxsize=1)
def granted_effect_catalog():
    with gzip.open(DATA_ROOT / "granted-spell-effect-trees.json.gz", "rt") as stream:
        return json.load(stream)


@lru_cache(maxsize=1)
def merged_spell_effects():
    from .spell_audit import catalog as class_catalog
    from .combat_effect_runtime import _merge_effects

    return (
        _merge_effects(class_catalog()["effects"], granted_effect_catalog())
        if enabled()
        else class_catalog()["effects"]
    )


def enabled():
    return os.environ.get("WAKFU_NATIVE_GRANTED_CAST", "0") == "1"
