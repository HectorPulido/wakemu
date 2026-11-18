"""Pure, opt-in stealth mechanics for authenticated owned world programs.

The world adapter pins native floor, patrol poses and vision cells, qualifies
the owner's path and actual rear-strike requests, and declares the turn
boundary. Neither an ordinary kill nor a client success flag is an input.
A declaration's turn schedule is an explicit reconstruction when original
scheduling is unavailable.
"""

from copy import deepcopy
from hashlib import sha256
import json


SCHEMA = "owned-world-stealth-trial-v1"
TERMINAL = {"success", "failed", "declined"}


def _point(value):
    return (
        isinstance(value, (list, tuple))
        and len(value) == 3
        and all(type(item) is int for item in value)
    )


def digest(config):
    return sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate(config):
    if (
        type(config) is not dict
        or config.get("schema") != SCHEMA
        or not isinstance(config.get("id"), str)
        or not config["id"]
        or not isinstance(config.get("evidence"), str)
        or not config["evidence"].strip()
        or not isinstance(config.get("cells"), list)
        or not config["cells"]
        or any(not _point(point) for point in config["cells"])
        or len(set(map(tuple, config["cells"]))) != len(config["cells"])
    ):
        raise ValueError("Stealth trial requires its finite source-qualified floor")
    cells = set(map(tuple, config["cells"]))
    if (
        not _point(config.get("start"))
        or tuple(config["start"]) not in cells
        or not isinstance(config.get("exits"), list)
        or not config["exits"]
        or any(
            not _point(point) or tuple(point) not in cells for point in config["exits"]
        )
        or tuple(config["start"]) in set(map(tuple, config["exits"]))
        or not isinstance(config.get("edges"), list)
        or not config["edges"]
        or any(
            not isinstance(edge, list)
            or len(edge) != 2
            or any(not _point(point) or tuple(point) not in cells for point in edge)
            or edge[0] == edge[1]
            for edge in config["edges"]
        )
        or config.get("turn_boundary") != "authenticated_turn"
        or type(config.get("detection_radius")) is not int
        or config["detection_radius"] <= 0
        or type(config.get("suspicion_turns")) is not int
        or config["suspicion_turns"] <= 0
        or type(config.get("rear_hits")) is not int
        or config["rear_hits"] <= 0
        or type(config.get("alert_radius")) is not int
        or config["alert_radius"] <= 0
        or type(config.get("neutralize_all_success")) is not bool
        or not isinstance(config.get("guards"), list)
        or not config["guards"]
    ):
        raise ValueError(
            "Stealth trial requires exact endpoints, turns and detection rules"
        )
    identities = set()
    for guard in config["guards"]:
        if (
            type(guard) is not dict
            or type(guard.get("id")) is not int
            or guard["id"] <= 0
            or guard["id"] in identities
            or not isinstance(guard.get("patrol"), list)
            or not guard["patrol"]
        ):
            raise ValueError(
                "Stealth guards require unique identities and explicit patrol poses"
            )
        identities.add(guard["id"])
        for pose in guard["patrol"]:
            if (
                type(pose) is not dict
                or not _point(pose.get("position"))
                or tuple(pose["position"]) not in cells
                or not _point(pose.get("rear_cell"))
                or tuple(pose["rear_cell"]) not in cells
                or sum(
                    abs(pose["position"][axis] - pose["rear_cell"][axis])
                    for axis in (0, 1)
                )
                != 1
                or not isinstance(pose.get("vision_cells"), list)
                or any(
                    not _point(point) or tuple(point) not in cells
                    for point in pose["vision_cells"]
                )
            ):
                raise ValueError(
                    "Stealth patrol pose requires its exact rear and vision floors"
                )
    return config


def begin(config, position, *, attempt=1):
    validate(config)
    if list(position) != config["start"] or type(attempt) is not int or attempt <= 0:
        raise ValueError(
            "Stealth attempt must begin at its authenticated starting floor"
        )
    return dict(
        schema=SCHEMA,
        profile_sha256=digest(config),
        attempt=attempt,
        stage="active",
        position=list(position),
        turns=0,
        guards={
            str(guard["id"]): dict(patrol_index=0, suspicion=0, hits=0)
            for guard in config["guards"]
        },
    )


def _pose(guard, state):
    return guard["patrol"][state["patrol_index"]]


def _distance(left, right):
    return sum(abs(left[axis] - right[axis]) for axis in (0, 1))


def advance(config, state, event):
    """Reduce trusted movement, explicit turns, qualified rear strikes or decline.

    Only the caller may turn native server actions into these events. Moving
    through several accepted cells checks every cell; waiting is not a turn.
    The reducer returns effects as facts for the caller's existing transaction.
    """
    validate(config)
    if (
        type(state) is not dict
        or state.get("schema") != SCHEMA
        or state.get("profile_sha256") != digest(config)
        or state.get("stage") not in TERMINAL | {"active"}
        or not _point(state.get("position"))
        or state["position"] not in config["cells"]
        or type(state.get("attempt")) is not int
        or state["attempt"] <= 0
        or type(state.get("turns")) is not int
        or state["turns"] < 0
        or not isinstance(state.get("guards"), dict)
        or set(state["guards"]) != {str(guard["id"]) for guard in config["guards"]}
    ):
        raise ValueError("Stealth state differs from its pinned attempt")
    for guard in config["guards"]:
        current = state["guards"][str(guard["id"])]
        if (
            type(current) is not dict
            or set(current) != {"patrol_index", "suspicion", "hits"}
            or any(type(value) is not int for value in current.values())
            or not 0 <= current["patrol_index"] < len(guard["patrol"])
            or not 0 <= current["hits"] <= config["rear_hits"]
            or not 0 <= current["suspicion"] <= config["suspicion_turns"]
        ):
            raise ValueError("Malformed durable stealth guard")
    if type(event) is not dict or event.get("kind") not in {
        "movement",
        "turn",
        "rear_strike",
        "decline",
    }:
        raise ValueError("Unknown stealth action")
    after = deepcopy(state)
    events = []
    if after["stage"] in TERMINAL:
        return dict(state=after, events=events)

    def active_guards():
        return [
            (guard, after["guards"][str(guard["id"])])
            for guard in config["guards"]
            if after["guards"][str(guard["id"])]["hits"] < config["rear_hits"]
        ]

    def fail(reason):
        after["stage"] = "failed"
        events.append(
            dict(kind="failure", reason=reason, return_position=list(config["start"]))
        )

    def observe():
        for guard, current in active_guards():
            pose = _pose(guard, current)
            if (
                after["position"] == pose["position"]
                or after["position"] in pose["vision_cells"]
            ):
                fail("vision")
                return False
        return True

    kind = event["kind"]
    if kind == "decline":
        after["stage"] = "declined"
        events.append(dict(kind="declined"))
    elif kind == "movement":
        path = event.get("cells")
        if (
            not isinstance(path, list)
            or not path
            or path[0] != after["position"]
            or any(not _point(point) for point in path)
            or any(
                [list(left), list(right)] not in config["edges"]
                for left, right in zip(path, path[1:])
            )
        ):
            raise ValueError("Stealth movement needs its actual contiguous native path")
        for point in path[1:]:
            after["position"] = list(point)
            if not observe():
                break
            if after["position"] in config["exits"]:
                after["stage"] = "success"
                events.append(dict(kind="success", reason="exit"))
                break
    elif kind == "turn":
        after["turns"] += 1
        for guard, current in active_guards():
            # A declaration pins one pose per real external turn. Cinematic
            # movement timings must not be mislabeled as this turn authority.
            current["patrol_index"] = (current["patrol_index"] + 1) % len(
                guard["patrol"]
            )
        if observe():
            for guard, current in active_guards():
                near = (
                    _distance(after["position"], _pose(guard, current)["position"])
                    < config["detection_radius"]
                )
                current["suspicion"] = current["suspicion"] + 1 if near else 0
                if current["suspicion"] >= config["suspicion_turns"]:
                    fail("proximity")
                    break
    else:
        selected = next(
            (
                (guard, current)
                for guard, current in active_guards()
                if guard["id"] == event.get("guard_id")
            ),
            None,
        )
        if selected is None or after["position"] != _pose(*selected)["rear_cell"]:
            raise ValueError(
                "Stealth strike requires its actual active guard's rear floor"
            )
        guard, current = selected
        current["hits"] += 1
        events.append(dict(kind="rear_hit", guard_id=guard["id"], hits=current["hits"]))
        if current["hits"] == config["rear_hits"]:
            position = _pose(guard, current)["position"]
            if any(
                _distance(position, _pose(other, status)["position"])
                < config["alert_radius"]
                for other, status in active_guards()
            ):
                fail("nearby_guard_alert")
            else:
                events.append(dict(kind="guard_neutralized", guard_id=guard["id"]))
                if config["neutralize_all_success"] and not active_guards():
                    after["stage"] = "success"
                    events.append(dict(kind="success", reason="guards"))
    return dict(state=after, events=events)
