"""Shared transaction-independent mission objective transitions.

Callers must authenticate and qualify events before invoking this function.
Persistence and reward delivery remain in the existing achievement service.
"""

from . import native_effective_eligibility

from copy import deepcopy


class ObjectivePrerequisiteUnavailable(ValueError):
    """A real activity occurred before its native mission objective was ready."""


def auto_track(state, identity):
    """Track a newly accepted mission, preserving existing tracking at capacity."""
    if type(identity) is not int or identity <= 0 or identity not in state["running"]:
        raise ValueError("Only an active mission can be tracked")
    from . import lifecycle

    lifecycle.retain_activation(state)
    tracked = set(state["tracking"])
    if identity not in tracked and len(tracked) < 255:
        state["tracking"] = sorted(tracked | {identity})


def seed_counters(state, definition):
    """Initialise a freshly activated mission's native counters, as the server does.

    The original journal announces each counter of an activated mission with an
    absolute zero before its activation packets, so the tracker can render
    "0/3" immediately. Existing values are never overwritten.
    """
    seeded = []
    for objective in definition.get("cjJ") or ():
        for condition in objective.get("ckf") or ():
            for source in condition.get("ckn") or ():
                key = str(source)
                if type(source) is not int or source <= 0 or key in state["variables"]:
                    continue
                state["variables"][key] = 0
                seeded.append(source)
    return seeded


def advance_objective(state, definition, objective_id, *, character, store, now_ms):
    """Advance one qualified objective; never starts a quest or invents events."""
    from wakfu_server.dungeon_achievement_authority import queries_from_state
    from wakfu_server import dungeon_criteria

    if (
        type(objective_id) is not int
        or objective_id <= 0
        or type(now_ms) is not int
        or now_ms < 0
        or definition.get("native_class") != "aJM"
        or definition.get("aqb") is not False
    ):
        raise ValueError("Invalid native quest objective transition")
    identity = definition["d"]
    objectives = {r["d"]: r for r in definition["cjJ"]}
    if len(objectives) != len(definition["cjJ"]) or objective_id not in objectives:
        raise ValueError("Missing or duplicate native quest objective")
    candidate = deepcopy(state)
    if identity in candidate["completed"] or objective_id in candidate["objectives"]:
        return candidate, [], [], []
    if identity not in candidate["running"]:
        raise ObjectivePrerequisiteUnavailable(
            "Native quest objective prerequisite: quest is not running"
        )
    from . import lifecycle

    lifecycle.retain_activation(candidate)
    queries = queries_from_state(candidate)
    objective = objectives[objective_id]
    for criterion in (
        native_effective_eligibility.criterion(definition),
        objective["ckc"],
        objective["cke"],
    ):
        if not dungeon_criteria.evaluate(
            store, criterion, character=character, queries=queries
        ):
            raise ObjectivePrerequisiteUnavailable(
                "Native quest objective prerequisite is not met"
            )
    candidate["objectives"] = sorted(set(candidate["objectives"]) | {objective_id})
    completed, intents = [], []
    if set(objectives) <= set(candidate["objectives"]):
        candidate["running"].remove(identity)
        candidate["completed"] = sorted(set(candidate["completed"]) | {identity})
        candidate["completion_dates"][str(identity)] = now_ms
        candidate["recent"] = (
            candidate["recent"] + [{"id": identity, "date_ms": now_ms}]
        )[-255:]
        candidate["tracking"] = [i for i in candidate["tracking"] if i != identity]
        completed = [identity]
        intents = [(identity, deepcopy(r)) for r in definition["cjK"]]
    return candidate, intents, [objective_id], completed
