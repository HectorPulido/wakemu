"""fyS cast accounting: reference identity, target footprint, turn and interval."""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from wakfu_server.paths import DATA_ROOT
from .combat_conditions import evaluate_condition, UnknownCondition


@lru_cache(maxsize=1)
def native_limits():
    return protocol_catalog.load(DATA_ROOT / "native-spell-limits.json")["spells"]


def limits(reference, level, context=None):
    row = native_limits().get(str(reference))
    if row is None or not 0 <= level <= row["maximum_level"]:
        raise ValueError("Missing native casting limit definition")
    baseline = tuple(row["limits"])
    tables = [baseline, *(tuple(r["limits"]) for r in row["conditional"])]
    if any(
        len(values) != 4
        or any(type(v) is not int or not -128 <= v <= 127 for v in values)
        for values in tables
    ):
        raise ValueError("Native casting limits must contain narrowed signed bytes")
    matches = set()
    unknown = False
    unknown_baseline = False
    for alternative in row["conditional"]:
        values = tuple(alternative["limits"])
        try:
            if context is None:
                raise UnknownCondition("Missing native conditional casting context")
            selected = evaluate_condition(alternative["criteria"], context)
        except UnknownCondition:
            if values == baseline:
                unknown_baseline = True
            else:
                unknown = True
            continue
        if selected:
            matches.add(values)
    if (
        unknown
        or len(matches) > 1
        or (unknown_baseline and any(values != baseline for values in matches))
    ):
        raise UnknownCondition("Unresolved native conditional casting limits")
    per_target, base, growth, interval = next(iter(matches), baseline)
    # fyG.b narrows the floor of base + growth * cmZ to signed byte.
    per_turn = (base + growth * level + 128) % 256 - 128
    return dict(per_target=per_target, per_turn=per_turn, interval=interval)


def validate_usage(fight, caster, reference, level, cell, context=None):
    callback = getattr(context, "native_usage_context_query", None)
    null_context = callback(None, reference, level) if callable(callback) else context
    rule = limits(reference, level, null_context)
    rows = getattr(fight, "native_spell_usage", {})
    state = rows.get(str(caster.id), {})
    same_turn = state.get("turn") == caster.turn_count
    key = str(reference)
    last = state.get("last", {}).get(key)
    if last is not None and rule["interval"] != 0:
        if rule["interval"] < 0 or fight.native_table_turn - last < rule["interval"]:
            raise ValueError("Native spell cast interval has not elapsed")
    if (
        same_turn
        and rule["per_turn"] > 0
        and state.get("casts", {}).get(key, 0) >= rule["per_turn"]
    ):
        raise ValueError("Native spell maximum casts per turn reached")
    targets = []
    definition = native_limits()[str(reference)]
    has_target_limit = rule["per_target"] > 0 or any(
        alternative["limits"][0] > 0 for alternative in definition["conditional"]
    )
    if has_target_limit or definition["conditional"]:
        from .combat_usage_targets import usage_targets

        for candidate in usage_targets(fight, cell):
            selected_context = (
                callback(candidate.identity, reference, level)
                if callable(callback)
                else context
            )
            selected_rule = limits(reference, level, selected_context)
            if (
                same_turn
                and selected_rule["per_turn"] > 0
                and state.get("casts", {}).get(key, 0) >= selected_rule["per_turn"]
            ):
                raise ValueError("Native spell maximum casts per turn reached")
            if selected_rule["per_target"] <= 0:
                continue
            target = str(candidate.identity)
            if (
                same_turn
                and state.get("targets", {}).get(key, {}).get(target, 0)
                >= selected_rule["per_target"]
            ):
                raise ValueError("Native spell maximum casts per target reached")
            if candidate.consume:
                targets.append(target)
    return dict(rule, targets=targets)


def consume_usage(fight, plan):
    """Called only on a successful transaction preview, including no-op casts."""
    caster = fight.actors[plan["actor_id"]]
    rows = getattr(fight, "native_spell_usage", None)
    if rows is None:
        rows = fight.native_spell_usage = {}
    state = rows.setdefault(str(caster.id), {"last": {}})
    if state.get("turn") != caster.turn_count:
        state.update(turn=caster.turn_count, casts={}, targets={})
    key = str(plan["spell_id"])
    rule = plan["native_usage"]
    if rule["interval"] != 0:
        state["last"][key] = fight.native_table_turn
    if rule["per_turn"] > 0:
        state["casts"][key] = state["casts"].get(key, 0) + 1
    for target in rule["targets"]:
        targets = state["targets"].setdefault(key, {})
        targets[target] = targets.get(target, 0) + 1
