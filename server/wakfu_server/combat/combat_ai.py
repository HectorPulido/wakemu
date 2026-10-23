"""TCP client for the separate monster planner; execution stays authoritative."""
from .combat_effective_control import effective_server_controlled
import hashlib
import json
import uuid
from .combat_ai_transport import request as request_ai


def snapshot(fight, actor_id):
    if fight.current is None or fight.current.id != actor_id:
        raise ValueError("AI actor is not current")
    actor = fight.actors[actor_id]
    if not effective_server_controlled(fight, actor) or actor.hp <= 0:
        raise ValueError("AI requires a living server-controlled actor")
    if fight.edges is None:
        raise ValueError("AI requires verified movement edges")
    state = dict(
        protocol=1,
        fight_id=fight.id,
        actor_id=actor_id,
        current_id=actor_id,
        walkable=[list(c) for c in sorted(fight.walkable)],
        edges=[[list(a), list(b)] for a, b in sorted(fight.edges)],
        actors=[
            dict(
                id=a.id,
                team=a.team,
                hp=a.hp,
                controlled=a.controlled,
                position=list(a.position),
                mp=a.mp,
                ap=a.ap,
            )
            for a in sorted(fight.actors.values(), key=lambda a: a.id)
        ],
    )
    state["stateKey"] = hashlib.sha256(
        json.dumps(state, sort_keys=True).encode()
    ).hexdigest()
    state["requestId"] = uuid.uuid4().hex
    return state


def validate(fight, actor_id, request, response):
    if snapshot(fight, actor_id)["stateKey"] != request["stateKey"]:
        raise ValueError("Combat state changed while AI was deciding")
    if (
        not isinstance(response, dict)
        or response.get("protocol") != 1
        or response.get("requestId") != request["requestId"]
        or response.get("stateKey") != request["stateKey"]
    ):
        raise ValueError("AI response does not match current request")
    decision = response.get("decision")
    if (
        not isinstance(decision, dict)
        or decision.get("actor_id") != actor_id
        or decision.get("attack") is not None
    ):
        raise ValueError("Unsupported AI decision")
    path = decision.get("path")
    actor = fight.actors[actor_id]
    if not isinstance(path, list) or len(path) > actor.mp:
        raise ValueError("Invalid AI movement budget")
    occupied = {
        a.position for a in fight.actors.values() if a.id != actor_id and a.hp > 0
    }
    previous = actor.position
    verified = []
    for cell in path:
        if (
            not isinstance(cell, (list, tuple))
            or len(cell) != 3
            or any(type(n) is not int for n in cell)
        ):
            raise ValueError("Invalid AI movement coordinate")
        cell = tuple(cell)
        if (
            cell not in fight.walkable
            or cell in occupied
            or (previous, cell) not in fight.edges
            or abs(cell[0] - previous[0]) + abs(cell[1] - previous[1]) != 1
        ):
            raise ValueError("AI selected an illegal movement edge")
        verified.append(cell)
        previous = cell
    target_id = decision.get("target_id")
    if target_id is not None:
        target = fight.actors.get(target_id)
        if target is None or target.hp <= 0 or target.team == actor.team:
            raise ValueError("AI selected an invalid target")
    return dict(
        actor_id=actor_id,
        target_id=target_id,
        path=verified,
        attack=None,
        reason=str(decision.get("reason", "Separate AI service"))[:256],
    )


def plan(fight, actor_id):
    request = snapshot(fight, actor_id)
    try:
        return validate(fight, actor_id, request, request_ai("/v1/decide", request))
    except (OSError, ValueError, TypeError) as error:
        # No in-process planner fallback: an unavailable service cannot propose
        # movement. The existing authoritative attack/end-turn handling remains.
        return dict(
            actor_id=actor_id,
            target_id=None,
            path=[],
            attack=None,
            reason="AI service unavailable or invalid response: "
            + type(error).__name__,
        )
