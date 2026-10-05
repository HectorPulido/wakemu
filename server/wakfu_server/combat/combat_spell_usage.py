"""fyS cast accounting: reference identity, target footprint, turn and interval."""
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_conditions import evaluate_condition, UnknownCondition


@lru_cache(maxsize=1)
def native_limits():
    return json.loads((DATA_ROOT / "native-spell-limits.json").read_text())["spells"]


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
    for alternative in row["conditional"]:
        values = tuple(alternative["limits"])
        if values == baseline:
            continue
        try:
            selected = evaluate_condition(alternative["criteria"], context)
        except UnknownCondition:
            unknown = True
            continue
        if selected:
            matches.add(values)
    if unknown or len(matches) > 1:
        raise UnknownCondition("Unresolved native conditional casting limits")
    per_target, base, growth, interval = next(iter(matches), baseline)
    # fyG.b narrows the floor of base + growth * cmZ to signed byte.
    per_turn = (base + growth * level + 128) % 256 - 128
    return dict(per_target=per_target, per_turn=per_turn, interval=interval)


def validate_usage(fight, caster, reference, level, cell, context=None):
    rule = limits(reference, level, context)
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
    if rule["per_target"] > 0:
        for actor in fight.actors.values():
            radius = actor.physical_radius
            if type(radius) is not int:
                raise ValueError("Missing native target footprint for casting limits")
            if (
                max(0, abs(actor.position[0] - cell[0]) - radius)
                + max(0, abs(actor.position[1] - cell[1]) - radius)
                == 0
            ):
                target = str(actor.id)
                targets.append(target)
                if (
                    same_turn
                    and state.get("targets", {}).get(key, {}).get(target, 0)
                    >= rule["per_target"]
                ):
                    raise ValueError("Native spell maximum casts per target reached")
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
