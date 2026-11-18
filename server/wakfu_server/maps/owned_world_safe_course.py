"""Pure accepted-movement courses over original floors and literal hazard cells."""
from copy import deepcopy
from hashlib import sha256
import json

SCHEMA = "owned-world-safe-course-v1"


def digest(config):
    return sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _point(p):
    return isinstance(p, list) and len(p) == 3 and all(type(n) is int for n in p)


def validate(trial, sources=None):
    config = trial.get("program")
    if (
        type(config) is not dict
        or config.get("schema") != SCHEMA
        or not config.get("id")
        or not config.get("evidence")
        or not isinstance(config.get("cells"), list)
        or not config["cells"]
        or any(not _point(p) for p in config["cells"])
        or len(set(map(tuple, config["cells"]))) != len(config["cells"])
        or not _point(config.get("start"))
        or config["start"] not in config["cells"]
        or not isinstance(config.get("exit_cells"), list)
        or not config["exit_cells"]
        or any(not _point(p) or p not in config["cells"] for p in config["exit_cells"])
        or config["start"] in config["exit_cells"]
        or not isinstance(config.get("hazard_cells"), list)
        or any(not _point(p) for p in config["hazard_cells"])
        or not isinstance(config.get("edges"), list)
        or not config["edges"]
        or any(
            not isinstance(e, list)
            or len(e) != 2
            or any(not _point(p) or p not in config["cells"] for p in e)
            for e in config["edges"]
        )
        or trial.get("sources", []) != []
    ):
        raise ValueError(
            "Safe course requires its exact floor, hazards and physical endpoints"
        )
    return config


def advance(trial, current, event):
    config = validate(trial)
    after = deepcopy(current)
    before = deepcopy(current)
    if event.get("kind") != "movement":
        return dict(
            state=after,
            changed=False,
            begin=False,
            success=False,
            failure=False,
            events=[],
        )
    path = event.get("cells")
    if not isinstance(path, list) or not path or any(not _point(p) for p in path):
        raise ValueError("Safe course requires the actual accepted movement path")
    program = after.get("program")
    begin = False
    if program is None or program["stage"] in ("failed", "declined"):
        index = next((i for i, p in enumerate(path) if p == config["start"]), None)
        if index is None:
            return dict(
                state=after,
                changed=False,
                begin=False,
                success=False,
                failure=False,
                events=[],
            )
        path = path[index:]
        program = dict(
            profile_sha256=digest(config),
            stage="active",
            position=list(config["start"]),
            attempt=1 if program is None else program["attempt"] + 1,
        )
        begin = True
    if (
        program.get("profile_sha256") != digest(config)
        or program.get("position") not in config["cells"]
    ):
        raise ValueError("Safe course checkpoint lost its source-pinned floor")
    if program["stage"] == "active":
        if path[0] != program["position"]:
            raise ValueError(
                "Safe course movement does not continue its actual position"
            )
        edges = {tuple(map(tuple, e)) for e in config["edges"]}
        hazards = set(map(tuple, config["hazard_cells"]))
        for origin, target in zip(path, path[1:]):
            if origin == target:
                continue
            if target not in config["cells"]:
                program["stage"] = "failed"
                break
            if (tuple(origin), tuple(target)) not in edges:
                raise ValueError("Safe course movement is not a native floor edge")
            program["position"] = list(target)
            if tuple(target) in hazards:
                program["stage"] = "failed"
                break
            if target in config["exit_cells"]:
                program["stage"] = "success"
                break
    after["program"] = program
    return dict(
        state=after,
        changed=after != before,
        begin=begin,
        success=program["stage"] == "success",
        failure=program["stage"] == "failed",
        events=[],
    )


def feedback(trial, current):
    program = current.get("program")
    if program is None:
        return []
    text = {
        "active": "Stay on the safe floor and reach the archaeologist.",
        "failed": "The floor gives way. Return to the marked entrance and try again.",
        "success": "You reached the archaeologist safely.",
    }.get(program["stage"])
    return [] if text is None else [dict(kind="information", text=text)]
