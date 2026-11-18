"""Reviewed Bworkball caller policy after an actual paid carrier step.

Original eXA802 supplies reciprocal pGN identities, not a coordinate producer.
This scene-only join moves the original ball to its carrier's committed endpoint
through the ordinary QI writer and delivers the real area callbacks. It never
changes the generic runner, creates a carry relation, or charges the ball MP.
"""
from .combat_scene_ball_goals import _areas, _ball, _scene
from contextvars import ContextVar


_peer_movement = ContextVar("native_ball_follow_area_boundary", default=None)


def peer_movement_authorized(fight, *, actor_id, origin, path):
    """Identify only the forced peer callback inside the verified follow join."""
    scope = _peer_movement.get()
    if scope is None or len(path) != 1:
        return False
    owner, carrier_id, ball_id, turn_id, start, endpoint = scope
    carrier, ball = fight.actors.get(carrier_id), fight.actors.get(ball_id)
    links = getattr(fight, "native_movement_links", {})
    return (
        owner is fight
        and actor_id == ball_id
        and fight.turn_id == turn_id
        and fight.phase == "active"
        and fight.current is carrier
        and carrier is not None
        and ball is not None
        and fight._in_play(carrier)
        and fight._in_play(ball)
        and carrier.position == ball.position == endpoint
        and tuple(origin) == start
        and tuple(path[0]) == endpoint
        and links.get(carrier_id) == ball_id
        and links.get(ball_id) == carrier_id
    )


def follow_paid_walk(fight, *, moving_id, origin, destination, area_events):
    """Return peer presentation/callback packets inside the paid-step preview.

    ``area_events(fight, ball, origin, destination)`` owns presentation followed
    by the existing native area provider/adopt boundary. A callback failure
    aborts the enclosing movement preview, including this QI relocation.
    """
    record, selected = _scene(fight)
    if selected is None:
        return []
    from .combat_movement_payment_events import _step_payment
    from .combat_qi_fight import current_registry, move_registered_actor

    carrier = fight.actors.get(moving_id)
    ball = _ball(fight, record, selected)
    links = getattr(fight, "native_movement_links", {})
    if (
        carrier is None
        or carrier is ball
        or links.get(moving_id) != ball.id
        or links.get(ball.id) != moving_id
    ):
        return []
    # A native callback may kill or displace the carrier, unlink the peer, or
    # finish the match. Such a step has no surviving carrier to follow.
    endpoint = tuple(destination)
    if (
        fight.phase != "active"
        or fight.current is not carrier
        or not fight._in_play(carrier)
        or not fight._in_play(ball)
        or carrier.position != endpoint
    ):
        return []
    payment = _step_payment.get()
    if (
        payment is None
        or payment["fight"] is not fight
        or payment["fight_id"] != fight.id
        or payment["actor_id"] != moving_id
        or payment["turn_id"] != fight.turn_id
        or payment["origin"] != tuple(origin)
        or payment["destination"] != endpoint
        or payment["mp_paid"] <= 0
    ):
        return []
    floor = set(map(tuple, record["room_cells"]))
    start = tuple(ball.position)
    if (
        start not in floor
        or endpoint not in floor
        or tuple(origin) not in floor
        or start[2] != endpoint[2]
        or max(abs(start[0] - origin[0]), abs(start[1] - origin[1])) > 1
    ):
        raise ValueError("Ball follow left its admitted native floor or linked carrier")
    if start == endpoint:
        return []
    if not callable(area_events):
        raise ValueError("Ball follow requires actual native area callbacks")
    _areas(fight, selected)
    registry = current_registry(fight)
    if not registry.terrain.aK(*endpoint[:2]):
        raise ValueError("Ball follow endpoint is outside native QI terrain")
    move_registered_actor(fight, ball, endpoint)
    # The carrier's receipt remains available to its outer scope, even after
    # consume_step_payment. The forced peer callback has no payment authority.
    token = _step_payment.set(None)
    peer_token = _peer_movement.set(
        (fight, moving_id, ball.id, fight.turn_id, start, endpoint)
    )
    try:
        return list(area_events(fight, ball, start, endpoint))
    finally:
        _peer_movement.reset(peer_token)
        _step_payment.reset(token)
