"""Client 12161 movement through authoritative FSM and native animation.

Serializer callback receives the updated actor and must serialize its owned
fight data. No captured stats are accepted implicitly.
"""
import struct
from .combat_movement import movement
from .combat_wire import actor_state


# Native actor directions use the eight adjacent planar cell vectors. This is
# the same ordering used by the client's oriented-area transform (anI/ana).
_DIRECTION_VECTORS = (
    (1, -1),
    (1, 0),
    (1, 1),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (-1, -1),
    (0, -1),
)


def direction_after_path(origin, path, current_direction):
    """Return the facing from the final planar step, preserving vertical-only moves."""
    previous = tuple(origin)
    direction = None
    for raw_cell in path:
        cell = tuple(raw_cell)
        if len(previous) != 3 or len(cell) != 3:
            raise ValueError("Invalid movement path cell")
        delta = (cell[0] - previous[0], cell[1] - previous[1])
        if delta != (0, 0):
            try:
                direction = _DIRECTION_VECTORS.index(delta)
            except ValueError as error:
                raise ValueError("Movement step has no native facing vector") from error
        previous = cell
    if direction is None:
        if type(current_direction) is not int or not 0 <= current_direction <= 7:
            raise ValueError("Missing authoritative current actor direction")
        direction = current_direction
    return direction


def decode_request(body):
    if not isinstance(body, bytes) or len(body) < 18 or (len(body) - 8) % 10:
        raise ValueError("Malformed combat movement request")
    actor_id = struct.unpack_from(">q", body)[0]
    path = list(struct.iter_unpack(">iih", body[8:]))
    if len(path) > 6552:
        raise ValueError("Movement path too long")
    return actor_id, path


def apply_client(runtime, owner_id, body, stats_serializer, *, area_provider=None):
    if area_provider is not None:
        return _with_areas(
            runtime,
            area_provider,
            lambda candidate: apply_client(candidate, owner_id, body, stats_serializer),
        )
    if runtime.awaiting_ack is not None:
        raise ValueError("Waiting for previous turn synchronization")
    actor_id, path = decode_request(body)
    fight = runtime.fight
    actor = fight._current_owned(owner_id, actor_id)
    origin = actor.position
    direction = direction_after_path(origin, path, getattr(actor, "direction", None))
    # Serialize anticipated owned state before committing, so codec failure
    # cannot spend MP or strand the actor. The FSM still validates every edge.
    import copy

    candidate = copy.deepcopy(actor)
    candidate.position = path[-1]
    candidate.direction = direction
    candidate.mp -= len(path)
    if candidate.mp < 0:
        raise ValueError("Insufficient MP")
    fight._sync_resources(candidate)
    stats = stats_serializer(candidate)
    animation = movement(
        fight.id, runtime.action_id + 1, actor_id, [origin, *path], direction
    )
    refresh = (12873, actor_state(12873, fight.id, actor_id, stats))
    event = fight.move(owner_id, actor_id, path)
    actor.direction = direction
    runtime.action_id += 1
    return [animation, runtime._flush(), refresh], event


def apply_ai(runtime, stats_serializer, *, direction, area_provider=None):
    """Plan and commit one server movement; attacking remains explicit policy."""
    if area_provider is not None:
        return _with_areas(
            runtime,
            area_provider,
            lambda candidate: apply_ai(
                candidate, stats_serializer, direction=direction
            ),
        )
    from .combat_ai import plan
    import copy

    if runtime.awaiting_ack is not None:
        raise ValueError("Waiting for previous turn synchronization")
    fight = runtime.fight
    if fight.current is None:
        raise ValueError("No active actor")
    actor = fight.current
    result = plan(fight, actor.id)
    path = result["path"]
    if not path:
        return [], result
    candidate = copy.deepcopy(actor)
    candidate.position = path[-1]
    candidate.direction = direction
    candidate.mp -= len(path)
    fight._sync_resources(candidate)
    stats = stats_serializer(candidate)
    animation = movement(
        fight.id, runtime.action_id + 1, actor.id, [actor.position, *path], direction
    )
    refresh = (12873, actor_state(12873, fight.id, actor.id, stats))
    result["event"] = fight.server_move(actor.id, path)
    actor.direction = direction
    runtime.action_id += 1
    return [animation, runtime._flush(), refresh], result


def _with_areas(runtime, provider, operation):
    from copy import deepcopy
    from .combat_area_boundary import adopt_runtime

    candidate = deepcopy(runtime)
    actor = candidate.fight.current
    if actor is None:
        raise ValueError("No active area movement actor")
    identity, origin = actor.id, tuple(actor.position)
    packets, result = operation(candidate)
    event = result.get("event", result)
    path = event.get("path", ())
    if path:
        preview, callbacks = provider(
            candidate.fight,
            actor_id=identity,
            action_id=candidate.action_id + 1,
            path=path,
            origin=origin,
        )
        candidate.fight = preview
        candidate.action_id += 1
        packets = list(packets) + list(callbacks)
        if callbacks:
            packets.append(candidate._flush())
    adopt_runtime(runtime, candidate)
    return packets, result
