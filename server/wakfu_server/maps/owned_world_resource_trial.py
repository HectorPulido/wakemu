"""Pure, durable resource-course reducer for authenticated owned world trials.

The caller qualifies ownership, native position/source and the transaction. It
persists the returned state together with movement and publishes events only
on commit. No event grants quests, inventory or ordinary combat victory.
"""

from copy import deepcopy

SCHEMA = "owned-world-resource-trial-v1"
TERMINAL = {"success", "failed", "declined"}


def _point(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(type(x) is int for x in value)
    )


def validate(config):
    if (
        type(config) is not dict
        or config.get("schema") != SCHEMA
        or not isinstance(config.get("id"), str)
        or not config["id"]
        or type(config.get("map_id")) is not int
        or config["map_id"] <= 0
        or not isinstance(config.get("cells"), list)
        or not config["cells"]
        or any(not _point(p) for p in config["cells"])
        or len({tuple(p) for p in config["cells"]}) != len(config["cells"])
    ):
        raise ValueError("Resource trial requires its finite native floor")
    cells = {tuple(p) for p in config["cells"]}
    if (
        not isinstance(config.get("edges"), list)
        or not config["edges"]
        or any(
            not isinstance(e, list)
            or len(e) != 2
            or any(not _point(p) or tuple(p) not in cells for p in e)
            or e[0] == e[1]
            for e in config["edges"]
        )
        or not _point(config.get("start"))
        or tuple(config["start"]) not in cells
        or not isinstance(config.get("chest_cells"), list)
        or not config["chest_cells"]
        or not isinstance(config.get("return_cells"), list)
        or not config["return_cells"]
        or any(
            not _point(p) or tuple(p) not in cells
            for p in config["chest_cells"] + config["return_cells"]
        )
        or set(map(tuple, config["chest_cells"]))
        & set(map(tuple, config["return_cells"]))
        or type(config.get("chest_source_id")) is not int
        or config["chest_source_id"] <= 0
        or type(config.get("capacity")) is not int
        or not 1 <= config["capacity"] <= 100
        or type(config.get("initial")) is not int
        or not 0 < config["initial"] <= config["capacity"]
        or config.get("tick_boundary") not in {"move", "explicit"}
        or type(config.get("decrement")) is not int
        or not 0 < config["decrement"] <= config["capacity"]
        or type(config.get("refill_threshold")) is not int
        or not 0 < config["refill_threshold"] <= config["capacity"]
        or type(config.get("refill_below")) is not int
        or config["refill_below"] <= 0
        or type(config.get("refill_at_or_above")) is not int
        or config["refill_at_or_above"] <= 0
        or not isinstance(config.get("bubbles"), list)
        or any(not _point(p) or tuple(p) not in cells for p in config["bubbles"])
        or len(set(map(tuple, config["bubbles"]))) != len(config["bubbles"])
        or config.get("bubble_policy") != "once_per_leg"
    ):
        raise ValueError(
            "Resource trial requires exact edges, resource rules and stage endpoints"
        )
    edges = {(tuple(a), tuple(b)) for a, b in config["edges"]}
    adjacency = {}
    for origin, target in edges:
        adjacency.setdefault(origin, set()).add(target)
    for origin, targets in (
        (tuple(config["start"]), set(map(tuple, config["chest_cells"]))),
        (tuple(config["chest_cells"][0]), set(map(tuple, config["return_cells"]))),
    ):
        reached = {origin}
        pending = [origin]
        while pending:
            p = pending.pop()
            for b in adjacency.get(p, ()):
                if b not in reached:
                    reached.add(b)
                    pending.append(b)
        if not targets <= reached:
            raise ValueError(
                "Resource trial endpoints are not connected by the declared native graph"
            )
    return config


def begin(config, position, *, attempt=1):
    validate(config)
    if (
        not _point(position)
        or list(position) != config["start"]
        or type(attempt) is not int
        or attempt <= 0
    ):
        raise ValueError(
            "Resource trial must begin at its authenticated starting floor"
        )
    return {
        "schema": SCHEMA,
        "trial_id": config["id"],
        "attempt": attempt,
        "stage": "outward",
        "position": list(position),
        "resource": config["initial"],
        "consumed_bubbles": [],
        "ticks": 0,
    }


def _state(config, state):
    if (
        type(state) is not dict
        or state.get("schema") != SCHEMA
        or state.get("trial_id") != config["id"]
        or type(state.get("attempt")) is not int
        or state["attempt"] <= 0
        or state.get("stage") not in TERMINAL | {"outward", "chest", "return"}
        or not _point(state.get("position"))
        or state["position"] not in config["cells"]
        or type(state.get("resource")) is not int
        or not 0 <= state["resource"] <= config["capacity"]
        or type(state.get("ticks")) is not int
        or state["ticks"] < 0
        or not isinstance(state.get("consumed_bubbles"), list)
        or any(type(k) is not str for k in state["consumed_bubbles"])
        or len(set(state["consumed_bubbles"])) != len(state["consumed_bubbles"])
    ):
        raise ValueError("Invalid durable resource trial state")


def advance(config, state, event):
    """Reduce one trusted action; transaction adapters must reject forged input.

    A move carries the caller's actual old/new native position. Explicit ticks
    are permitted only for a configured external turn producer. A chest action
    is valid only at a source-qualified approach after reaching the far side.
    Terminal receipts are inert, including reconnect/replayed chest actions.
    """
    validate(config)
    _state(config, state)
    if type(event) is not dict or event.get("kind") not in {
        "move",
        "tick",
        "chest",
        "decline",
    }:
        raise ValueError("Unknown resource trial action")
    next_state = deepcopy(state)
    events = []
    if state["stage"] in TERMINAL:
        return {"state": next_state, "events": events}
    kind = event["kind"]
    if kind == "decline":
        next_state["stage"] = "declined"
        return {"state": next_state, "events": ["declined"]}
    if kind == "chest":
        if (
            event.get("source_id") != config["chest_source_id"]
            or state["stage"] != "chest"
            or state["position"] not in config["chest_cells"]
        ):
            raise ValueError(
                "Chest requires actual outward course completion and native source"
            )
        next_state["stage"] = "return"
        return {"state": next_state, "events": ["chest_opened", "return_started"]}
    if kind == "tick" and config["tick_boundary"] != "explicit":
        raise ValueError("This course has no external resource tick producer")
    if kind == "move":
        if (
            not _point(event.get("from"))
            or not _point(event.get("to"))
            or list(event["from"]) != state["position"]
        ):
            raise ValueError("Movement must use the actual durable previous position")
        edge = [list(event["from"]), list(event["to"])]
        if edge not in config["edges"]:
            raise ValueError("Movement is outside the declared native course graph")
        next_state["position"] = list(event["to"])
        if state["stage"] == "chest":
            # The outward challenge has ended. Ordinary exploration remains
            # possible, but only the real chest action starts the return leg.
            return {"state": next_state, "events": []}
        bubble = next_state["position"]
        key = state["stage"] + ":" + ",".join(map(str, bubble))
        if bubble in config["bubbles"] and key not in next_state["consumed_bubbles"]:
            value = (
                config["refill_below"]
                if next_state["resource"] < config["refill_threshold"]
                else config["refill_at_or_above"]
            )
            next_state["resource"] = min(
                config["capacity"], next_state["resource"] + value
            )
            next_state["consumed_bubbles"].append(key)
            events.append("bubble_absorbed")
    if kind == "tick" or config["tick_boundary"] == "move":
        next_state["ticks"] += 1
        next_state["resource"] = max(0, next_state["resource"] - config["decrement"])
        events.append("resource_decremented")
    if next_state["resource"] == 0:
        next_state["stage"] = "failed"
        events.append("failure")
    elif (
        state["stage"] == "outward" and next_state["position"] in config["chest_cells"]
    ):
        next_state["stage"] = "chest"
        events.append("outward_arrived")
    elif (
        state["stage"] == "return" and next_state["position"] in config["return_cells"]
    ):
        next_state["stage"] = "success"
        events.append("success")
    return {"state": next_state, "events": events}
