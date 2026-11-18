"""Reusable, side-effect-free lifecycle for native periodic missions.

A caller must qualify and authenticate the event, serialize the character via
achievement storage, persist the cycle receipt and commit rewards atomically.
This module does not publish missions or decide which event completes them.
"""

from copy import deepcopy


def cycle_index(definition, now_ms, *, policy):
    """Return a cycle under an explicitly selected reconstructed boundary policy."""
    if policy != "fixed_native_anchor_v1":
        raise ValueError("Unsupported recurring cycle policy")
    if not isinstance(definition, dict) or type(now_ms) is not int or now_ms < 0:
        raise ValueError("Invalid recurring mission time")
    anchor = definition.get("cjT")
    period = definition.get("cjU")
    if (
        type(anchor) is not int
        or anchor < 0
        or type(period) is not int
        or period <= 0
        or now_ms < anchor
        or definition.get("aqb") is not False
        or not isinstance(definition.get("cjJ"), list)
        or not definition["cjJ"]
        or any(obj.get("ckf") for obj in definition["cjJ"])
    ):
        raise ValueError("Unsupported native recurring mission lifecycle")
    return (now_ms - anchor) // (period * 1000)


def reset(state, definition):
    """Remove only this definition's projection when a previous cycle expires."""
    candidate = deepcopy(state)
    identity = definition["d"]
    from . import lifecycle

    lifecycle.reset(candidate, identity)
    objective_ids = {obj["d"] for obj in definition["cjJ"]}
    for name in ("running", "completed", "tracking"):
        candidate[name] = [x for x in candidate[name] if x != identity]
    candidate["objectives"] = [
        x for x in candidate["objectives"] if x not in objective_ids
    ]
    candidate["completion_dates"].pop(str(identity), None)
    return candidate


def begin(state, definition, *, now_ms, previous_cycle, policy):
    """Plan an explicit acceptance; receipt is owned and persisted by caller.

    previous_cycle is the latest durable receipt's index, or None. A second
    acceptance in the same cycle returns unchanged state and False.
    """
    current = cycle_index(definition, now_ms, policy=policy)
    if previous_cycle is not None and (
        type(previous_cycle) is not int
        or previous_cycle < 0
        or previous_cycle > current
    ):
        raise ValueError("Invalid recurring mission receipt")
    if previous_cycle == current:
        return deepcopy(state), current, False
    candidate = (
        reset(state, definition) if previous_cycle is not None else deepcopy(state)
    )
    identity = definition["d"]
    if identity in candidate["running"] or identity in candidate["completed"]:
        raise ValueError("Existing recurring state lacks cycle authority")
    candidate["running"] = sorted(set(candidate["running"]) | {identity})
    from .mission_progress import auto_track

    auto_track(candidate, identity)
    return candidate, current, True


def finish(state, definition, objective_id, *, now_ms, accepted_cycle, policy):
    """Plan one event already qualified by an adapter; return native rewards.

    The adapter must check native criteria and costs, preserve this cycle's
    receipt and enqueue each reward with a cycle-scoped key in one transaction.
    """
    current = cycle_index(definition, now_ms, policy=policy)
    if type(accepted_cycle) is not int or accepted_cycle != current:
        raise ValueError("Recurring mission is not accepted in current cycle")
    objectives = {o["d"] for o in definition["cjJ"]}
    if len(objectives) != len(definition["cjJ"]) or objective_id not in objectives:
        raise ValueError("Invalid recurring mission objective")
    result = deepcopy(state)
    identity = definition["d"]
    if objective_id in result["objectives"]:
        return result, [], False
    if identity not in result["running"]:
        raise ValueError("Recurring mission is not running")
    from . import lifecycle

    lifecycle.retain_activation(result)
    result["objectives"] = sorted(set(result["objectives"]) | {objective_id})
    rewards = []
    if objectives <= set(result["objectives"]):
        result["running"].remove(identity)
        result["completed"] = sorted(set(result["completed"]) | {identity})
        result["tracking"] = [x for x in result["tracking"] if x != identity]
        result["completion_dates"][str(identity)] = now_ms
        result["recent"] = (result["recent"] + [{"id": identity, "date_ms": now_ms}])[
            -255:
        ]
        rewards = deepcopy(definition["cjK"])
    return result, rewards, True
