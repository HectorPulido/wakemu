"""Source-qualified sliding tiles driven by accepted adjacent owner movement.

The owner occupies the empty tile. Moving one native edge swaps that empty
tile with its neighbour. Board identity, target arrangement and source floor
are declarations; neither a client success flag nor an ordinary kill exists.
"""

from copy import deepcopy
from hashlib import sha256
import json


SCHEMA = "owned-world-tile-trial-v1"


def digest(config):
    return sha256(
        json.dumps(config, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate(config):
    if not isinstance(config, dict) or config.get("schema") != SCHEMA:
        raise ValueError("Unsupported sliding tile declaration")
    cells, initial, goal = (config.get(key) for key in ("cells", "initial", "goal"))
    if (
        not isinstance(cells, list)
        or not 4 <= len(cells) <= 64
        or any(
            not isinstance(p, list) or len(p) != 3 or any(type(v) is not int for v in p)
            for p in cells
        )
        or len(set(map(tuple, cells))) != len(cells)
        or not isinstance(initial, list)
        or not isinstance(goal, list)
        or len(initial) != len(cells)
        or len(goal) != len(cells)
        or any(type(v) is not int for v in initial + goal)
        or set(initial) != set(range(len(cells)))
        or set(goal) != set(initial)
        or not isinstance(config.get("evidence"), str)
        or not config["evidence"].strip()
    ):
        raise ValueError("Sliding tiles need an exact finite floor and permutations")
    edges = config.get("edges")
    if (
        not isinstance(edges, list)
        or not edges
        or any(
            not isinstance(edge, list)
            or len(edge) != 2
            or any(
                type(index) is not int or not 0 <= index < len(cells) for index in edge
            )
            or edge[0] == edge[1]
            or sum(abs(cells[edge[0]][axis] - cells[edge[1]][axis]) for axis in (0, 1))
            != 1
            for edge in edges
        )
    ):
        raise ValueError("Sliding tile edges require actual adjacent native floor")
    if len(set(map(tuple, edges))) != len(edges):
        raise ValueError("Duplicate sliding tile edge")
    if type(config.get("display_width", 4)) is not int or not 1 <= config.get(
        "display_width", 4
    ) <= len(cells):
        raise ValueError("Invalid sliding tile display width")
    return deepcopy(config)


def begin(config, position, *, attempt=1):
    validate(config)
    if type(attempt) is not int or attempt < 1:
        raise ValueError("Invalid sliding tile attempt")
    empty = config["initial"].index(0)
    if list(position) != config["cells"][empty]:
        raise ValueError("Sliding tile owner must occupy the original empty tile")
    return dict(
        schema=SCHEMA,
        profile_sha256=digest(config),
        tiles=list(config["initial"]),
        position=list(position),
        moves=0,
        attempt=attempt,
        stage="active",
    )


def advance(config, state, event):
    validate(config)
    if state.get("schema") != SCHEMA or state.get("profile_sha256") != digest(config):
        raise ValueError("Sliding tile state differs from its pinned board")
    after = deepcopy(state)
    if after.get("stage") != "active":
        return dict(state=after, events=[])
    if event.get("kind") == "decline":
        after["stage"] = "declined"
        return dict(state=after, events=[dict(kind="declined")])
    if event.get("kind") != "move" or event.get("from") != after["position"]:
        raise ValueError("Sliding tiles require the actual contiguous owner path")
    cells = list(map(tuple, config["cells"]))
    try:
        origin, target = cells.index(tuple(event["from"])), cells.index(
            tuple(event["to"])
        )
    except (ValueError, KeyError, TypeError) as error:
        raise ValueError("Sliding tile movement left the declared board") from error
    if [origin, target] not in config["edges"] or after["tiles"][origin] != 0:
        raise ValueError("Sliding tile movement is not a qualified adjacent swap")
    after["tiles"][origin], after["tiles"][target] = after["tiles"][target], 0
    after["position"] = list(event["to"])
    after["moves"] += 1
    events = [
        dict(
            kind="tile_swapped",
            origin=origin,
            target=target,
            tile=after["tiles"][origin],
            moves=after["moves"],
        )
    ]
    if after["tiles"] == config["goal"]:
        after["stage"] = "success"
        events.append(dict(kind="success"))
    return dict(state=after, events=events)
