"""Qualified Wakemu committed-step facts, separate from native null Qe."""
from contextlib import contextmanager

POLICY = "wakemu.committed-movement-recipient-v1"
_SCOPE = "_wakemu_committed_movement_recipient_scope"


def validate_movement_boundary_context(context, *, fight=None):
    if (
        not isinstance(context, dict)
        or set(context)
        != {
            "policy",
            "actor_id",
            "turn_id",
            "action_id",
            "from_cell",
            "to_cell",
            "event_id",
        }
        or context["policy"] != POLICY
        or type(context["actor_id"]) is not int
        or context["actor_id"] == 0
        or type(context["turn_id"]) is not int
        or type(context["action_id"]) is not int
        or not 0 < context["action_id"] < (1 << 31)
        or type(context["event_id"]) is not int
        or context["event_id"] != 1005
    ):
        raise ValueError("Invalid committed movement boundary facts")
    origin, destination = context["from_cell"], context["to_cell"]
    if (
        any(
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            for cell in (origin, destination)
        )
        or abs(origin[0] - destination[0]) + abs(origin[1] - destination[1]) != 1
    ):
        raise ValueError("Invalid committed movement boundary step")
    if fight is not None:
        actor = fight.actors.get(context["actor_id"])
        if (
            fight.phase != "active"
            or actor is None
            or actor is not fight.current
            or fight.turn_id != context["turn_id"]
            or tuple(actor.position) != tuple(destination)
            or tuple(origin) not in fight.walkable
            or tuple(destination) not in fight.walkable
        ):
            raise ValueError("Committed movement facts differ from actual participant")
        if fight.edges is not None:
            if (tuple(origin), tuple(destination)) not in fight.edges:
                raise ValueError("Committed movement lacks native terrain edge")
        elif origin[2] != destination[2]:
            raise ValueError("Committed altitude step lacks native terrain edge")
    return context


@contextmanager
def committed_movement_recipient_scope(fight, context):
    validate_movement_boundary_context(context, fight=fight)
    if getattr(fight, _SCOPE, None) is not None:
        raise ValueError("Nested committed movement recipient publication")
    setattr(fight, _SCOPE, context)
    try:
        yield
    finally:
        delattr(fight, _SCOPE)


def committed_movement_actor(fight, context):
    validate_movement_boundary_context(context, fight=fight)
    if getattr(fight, _SCOPE, None) is not context:
        raise ValueError("Unattested committed movement recipient publication")
    return fight.actors[context["actor_id"]]
