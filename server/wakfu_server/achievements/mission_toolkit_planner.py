"""Plan trusted producer events using published, native-validated declarations.

The domain producer authenticates ownership, validates actual gameplay, and
records its durable deduplication receipt in the settlement transaction. This
module neither authorizes client packets nor persists state or delivers rewards.
"""

from copy import deepcopy

from . import mission_dependencies, mission_progress
from .mission_toolkit_contract import (
    definitions_by_id,
    matches,
    validate,
    validate_event,
)


def _eligible(state, definition, objective, *, character, store, now_ms):
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

    authority = queries_from_snapshot(
        {key: state[key] for key in ("running", "completed", "objectives")}
    )
    try:
        return all(
            dungeon_criteria.evaluate(
                store,
                criterion,
                character=character,
                queries=authority,
                now_ms=now_ms,
            )
            for criterion in (definition["cjI"], objective["ckc"], objective["cke"])
        )
    except (ValueError, NotImplementedError, KeyError):
        return False


def _activate(state, definitions, declarations, events, *, character, store, now_ms):
    from wakfu_server import dungeon_criteria
    from wakfu_server.dungeon_achievement_authority import queries_from_snapshot

    changed = False
    for row in declarations:
        identity = row["quest_id"]
        if identity in state["running"] or identity in state["completed"]:
            continue
        if not set(row.get("requires_completed", ())) <= set(state["completed"]):
            continue
        if not any(matches(row, event, character) for event in events):
            continue
        authority = queries_from_snapshot(
            {key: state[key] for key in ("running", "completed", "objectives")}
        )
        definition = definitions[identity]
        try:
            eligible = dungeon_criteria.evaluate(
                store,
                definition["cjI"],
                character=character,
                queries=authority,
                now_ms=now_ms,
            )
        except (ValueError, NotImplementedError, KeyError):
            eligible = False
        if not eligible:
            continue
        state["running"] = sorted(set(state["running"]) | {identity})
        mission_progress.seed_counters(state, definition)
        mission_progress.auto_track(state, identity)
        changed = True
    return changed


def plan(state, definitions, profile, event, *, character, store, now_ms):
    """Return the common(state,intents,objectives,completed) settlement plan.

    Counter increments are aggregated by native variable identity, once per
    trusted operation. Quantity units stop contributing to a completed objective.
    Completed child events can activate explicitly declared follow-up missions.
    """
    from .counter_missions import bindings

    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid mission toolkit event time")
    if type(character.get("id")) is not int or type(character.get("map_id")) is not int:
        raise ValueError("Missing mission toolkit character context")
    by_id = definitions_by_id(definitions)
    profile = validate(profile, by_id)
    validate_event(event)
    candidate = deepcopy(state)
    intents, objectives, completed = [], [], []
    _activate(
        candidate,
        by_id,
        profile["activations"],
        [event],
        character=character,
        store=store,
        now_ms=now_ms,
    )
    # A quantity event is N native operations. Once all bound objectives
    # complete, remaining units are inert, matching legacy per-unit settlement.
    units = (
        event["quantity"]
        if any(
            row["count"] == "quantity" and matches(row, event, character)
            for row in profile["bindings"]
        )
        else 1
    )
    native_counters = bindings(list(by_id.values()))
    for unit in range(units):
        selected = [
            row
            for row in profile["bindings"]
            if matches(row, event, character)
            and (unit == 0 or row["count"] == "quantity")
            and row["quest_id"] in candidate["running"]
            and row["objective_id"] not in candidate["objectives"]
        ]
        if not selected:
            break
        targets = set()
        policies = {}
        increments = {}
        for row in selected:
            target = row["quest_id"], row["objective_id"]
            if target in targets:
                raise ValueError(
                    "Overlapping toolkit bindings match the same objective"
                )
            targets.add(target)
            if "variable_id" in row:
                variable = row["variable_id"]
                amount = 1
                if variable in policies and policies[variable] != row["count"]:
                    raise ValueError(
                        "Conflicting toolkit count policies for native variable"
                    )
                policies[variable] = row["count"]
                increments[variable] = amount
        for variable, amount in increments.items():
            value = candidate["variables"].get(str(variable), 0)
            if type(value) is not int or value < 0 or value + amount >= 2**63:
                raise ValueError("Invalid or overflowing native mission counter")
            candidate["variables"][str(variable)] = value + amount
        for row in selected:
            quest, objective_id = row["quest_id"], row["objective_id"]
            if quest not in candidate["running"]:
                continue
            definition = by_id[quest]
            objective = next(
                item for item in definition["cjJ"] if item["d"] == objective_id
            )
            if "variable_id" in row:
                variable = row["variable_id"]
                threshold = next(
                    item[3]
                    for item in native_counters[variable]
                    if item[:3] == (quest, objective_id, variable)
                )
                if candidate["variables"][str(variable)] < threshold:
                    continue
            if not _eligible(
                candidate,
                definition,
                objective,
                character=character,
                store=store,
                now_ms=now_ms,
            ):
                continue
            (
                candidate,
                added_intents,
                added_objectives,
                added_completed,
            ) = mission_progress.advance_objective(
                candidate,
                definition,
                objective_id,
                character=character,
                store=store,
                now_ms=now_ms,
            )
            intents.extend(added_intents)
            objectives.extend(added_objectives)
            completed.extend(added_completed)
    links = tuple(
        (row["parent_quest_id"], row["objective_id"], row["child_quest_id"])
        for row in profile["links"]
    )
    while True:
        (
            candidate,
            added_intents,
            added_objectives,
            added_completed,
        ) = mission_dependencies.reconcile(
            candidate,
            by_id,
            links,
            character=character,
            store=store,
            now_ms=now_ms,
        )
        intents.extend(added_intents)
        objectives.extend(added_objectives)
        completed.extend(added_completed)
        events = [event] + [
            dict(kind="quest_completed", reference=identity, quantity=1)
            for identity in completed
        ]
        activated = _activate(
            candidate,
            by_id,
            profile["activations"],
            events,
            character=character,
            store=store,
            now_ms=now_ms,
        )
        if not activated:
            return candidate, intents, objectives, completed
