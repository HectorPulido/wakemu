"""Pure unit-transition progress and reward planning for qualified achievements."""
from copy import deepcopy


def advance(state, event, rules, *, now_ms):
    """Return a new state and durable reward intents; never grants rewards here.

    The explicit local policy latches qualified objective milestones even before
    their prerequisite achievement completes. Definition completion still waits
    for all prerequisites. Each native equality is evaluated on every unit kill.
    """
    if type(now_ms) is not int or now_ms < 0:
        raise ValueError("Authoritative achievement timestamp required")
    candidate = deepcopy(state)
    objectives = set(candidate["objectives"])
    completed = set(candidate["completed"])
    prior_objectives, prior_completed = set(objectives), set(completed)
    by_variable, by_dungeon, by_breed = {}, {}, {}
    for rule in rules["definitions"].values():
        for objective in rule["objectives"]:
            if "variable_id" in objective:
                by_variable.setdefault(objective["variable_id"], []).append(objective)
            elif "breed_id" in objective:
                by_breed.setdefault(objective["breed_id"], []).append(objective)
            else:
                by_dungeon.setdefault(objective["dungeon_id"], []).append(objective)
    for breed in event["original_breeds"]:
        for objective in by_breed.get(breed, ()):
            objectives.add(objective["objective_id"])
        variable = rules["breed_variables"].get(breed)
        if variable is None:
            continue
        key = str(variable)
        value = candidate["variables"].get(key, 0) + 1
        if value >= 2**63:
            raise ValueError("Achievement variable overflow")
        candidate["variables"][key] = value
        for objective in by_variable[variable]:
            threshold = objective["threshold"]
            matched = (
                value == threshold
                if objective["operator"] == "=="
                else value >= threshold
                if objective["operator"] == ">="
                else value > threshold
            )
            if matched:
                objectives.add(objective["objective_id"])
    for objective in by_dungeon.get(event.get("completed_dungeon_id"), ()):
        objectives.add(objective["objective_id"])
    grants = []
    changed = True
    while changed:
        changed = False
        for identity, rule in rules["definitions"].items():
            if identity in completed or not set(rule["prerequisites"]) <= completed:
                continue
            if all(o["objective_id"] in objectives for o in rule["objectives"]):
                completed.add(identity)
                candidate["completion_dates"][str(identity)] = now_ms
                candidate["recent"].append({"id": identity, "date_ms": now_ms})
                grants.extend((identity, reward) for reward in rule["rewards"])
                changed = True
    candidate["recent"] = candidate["recent"][-255:]
    candidate["objectives"] = sorted(objectives)
    candidate["completed"] = sorted(completed)
    candidate["running"] = sorted(
        (set(candidate["running"]) | set(rules["definitions"])) - completed
    )
    candidate["tracking"] = [i for i in candidate["tracking"] if i not in completed]
    return (
        candidate,
        grants,
        sorted(objectives - prior_objectives),
        sorted(completed - prior_completed),
    )
