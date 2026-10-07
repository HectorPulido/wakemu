"""Wakfu legal movement candidates and deterministic BFS over native 3D edges.

The world supplies verified terrain and remains authoritative for execution.
There are no Dofus cells, spells, model files, LLM calls or inferred attacks.
"""
from collections import deque
from functools import lru_cache
import threading

_TACTICAL_IMPORT_LOCK = threading.Lock()


@lru_cache(maxsize=1)
def _tactical_planner():
    # Resolve sibling modules even when a host loads this file with importlib.
    # A private package also avoids collisions with unrelated search modules.
    import importlib.util
    from pathlib import Path
    import sys

    name = "_wakfu_ai_tactical"
    with _TACTICAL_IMPORT_LOCK:
        if name not in sys.modules:
            directory = Path(__file__).resolve().parent
            spec = importlib.util.spec_from_file_location(
                name,
                directory / "tactical.py",
                submodule_search_locations=[str(directory)],
            )
            module = importlib.util.module_from_spec(spec)
            sys.modules[name] = module
            try:
                spec.loader.exec_module(module)
            except Exception:
                sys.modules.pop(name, None)
                raise
        return sys.modules[name].decide


_REASON = "No reference-verified attack policy; movement only"


def _integer(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("Invalid " + name)
    return value


def _cell(value):
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("Invalid native position")
    return tuple(
        _integer(v, -(1 << (b - 1)), (1 << (b - 1)) - 1, "position coordinate")
        for v, b in zip(value, (32, 32, 16))
    )


def validate(snapshot, *, max_cells=8192, max_edges=65536):
    if (
        not isinstance(snapshot, dict)
        or type(snapshot.get("protocol")) is not int
        or snapshot["protocol"] != 1
    ):
        raise ValueError("Unsupported AI protocol")
    for field in ("requestId", "stateKey"):
        if (
            not isinstance(snapshot.get(field), str)
            or not 1 <= len(snapshot[field]) <= 512
        ):
            raise ValueError("Missing or invalid " + field)
    _integer(snapshot.get("fight_id"), 1, (1 << 31) - 1, "fight ID")
    actor_id = _integer(
        snapshot.get("actor_id"), -(1 << 63) + 1, (1 << 63) - 1, "actor ID"
    )
    if (
        actor_id == 0
        or snapshot.get("current_id") != actor_id
        or type(snapshot["current_id"]) is not int
    ):
        raise ValueError("AI actor is not current")
    raw_cells = snapshot.get("walkable")
    raw_edges = snapshot.get("edges")
    raw_actors = snapshot.get("actors")
    if not isinstance(raw_cells, list) or not 1 <= len(raw_cells) <= max_cells:
        raise ValueError("Invalid native walkable cells")
    cells = {_cell(c) for c in raw_cells}
    if len(cells) != len(raw_cells):
        raise ValueError("Duplicate native cell")
    if not isinstance(raw_edges, list) or len(raw_edges) > max_edges:
        raise ValueError("Invalid native movement edges")
    edges = set()
    for edge in raw_edges:
        if not isinstance(edge, list) or len(edge) != 2:
            raise ValueError("Invalid native movement edge")
        src, dst = (_cell(c) for c in edge)
        if src not in cells or dst not in cells:
            raise ValueError("Movement edge outside arena")
        edges.add((src, dst))
    if not isinstance(raw_actors, list) or not 1 <= len(raw_actors) <= 256:
        raise ValueError("Invalid actor roster")
    actors = {}
    occupied = set()
    for entry in raw_actors:
        if not isinstance(entry, dict):
            raise ValueError("Invalid actor")
        identity = _integer(
            entry.get("id"), -(1 << 63) + 1, (1 << 63) - 1, "actor identity"
        )
        if identity == 0 or identity in actors:
            raise ValueError("Duplicate or zero actor identity")
        if type(entry.get("controlled")) is not bool:
            raise ValueError("Invalid actor control flag")
        position = _cell(entry.get("position"))
        if position not in cells:
            raise ValueError("Actor outside walkable terrain")
        hp = _integer(entry.get("hp"), 0, (1 << 31) - 1, "actor HP")
        if hp > 0 and position in occupied:
            raise ValueError("Living actors overlap")
        if hp > 0:
            occupied.add(position)
        actors[identity] = dict(
            id=identity,
            team=_integer(entry.get("team"), 0, 255, "actor team"),
            hp=hp,
            controlled=entry["controlled"],
            position=position,
            mp=_integer(entry.get("mp"), 0, 32767, "actor MP"),
            ap=_integer(entry.get("ap"), 0, 32767, "actor AP"),
        )
    actor = actors.get(actor_id)
    if actor is None or actor["controlled"] or actor["hp"] <= 0:
        raise ValueError("AI requires a living server-controlled actor")
    return actor_id, actors, cells, edges


def legal_movements(cell, graph):
    """Explicit native directed edges; callers already removed occupied cells."""
    return sorted(graph.get(cell, ()))


def decide(snapshot):
    if (
        isinstance(snapshot, dict)
        and type(snapshot.get("protocol")) is int
        and snapshot["protocol"] == 2
    ):
        # Lazy import keeps the established protocol-1 boundary independent.
        return _tactical_planner()(
            snapshot, lambda value: validate(value, max_cells=32767, max_edges=131068)
        )
    actor_id, actors, walkable, edges = validate(snapshot)
    actor = actors[actor_id]
    enemies = [a for a in actors.values() if a["team"] != actor["team"] and a["hp"] > 0]
    occupied = {
        a["position"] for a in actors.values() if a["id"] != actor_id and a["hp"] > 0
    }
    graph = {}
    for source, target in edges:
        # Fight._move_actor requires a single cardinal step. The native edge
        # still proves the altitude transition; height is never guessed.
        if (
            target not in occupied
            and abs(source[0] - target[0]) + abs(source[1] - target[1]) == 1
        ):
            graph.setdefault(source, set()).add(target)
    queue = deque([actor["position"]])
    parents = {actor["position"]: None}
    goal = None
    target_id = None
    while queue:
        cell = queue.popleft()
        targets = sorted(
            (
                enemy
                for enemy in enemies
                if (cell, enemy["position"]) in edges
                and abs(cell[0] - enemy["position"][0])
                + abs(cell[1] - enemy["position"][1])
                == 1
            ),
            key=lambda a: a["id"],
        )
        if targets:
            goal = cell
            target_id = targets[0]["id"]
            break
        for following in legal_movements(cell, graph):
            if following not in parents:
                parents[following] = cell
                queue.append(following)
    path = []
    if goal is not None:
        cell = goal
        while parents[cell] is not None:
            path.append(cell)
            cell = parents[cell]
        path.reverse()
        path = path[: actor["mp"]]
    decision = dict(
        actor_id=actor_id,
        target_id=target_id,
        path=[list(c) for c in path],
        attack=None,
        reason=_REASON,
    )
    return dict(
        protocol=1,
        requestId=snapshot["requestId"],
        stateKey=snapshot["stateKey"],
        decision=decision,
    )
