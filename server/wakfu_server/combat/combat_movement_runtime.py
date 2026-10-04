"""Client 12161 movement through authoritative FSM and native animation.

Serializer callback receives the updated actor and must serialize its owned
fight data. No captured stats are accepted implicitly.
"""
import struct
from .combat_movement import movement
from .combat_wire import actor_state


def decode_request(body):
    if not isinstance(body, bytes) or len(body) < 18 or (len(body) - 8) % 10:
        raise ValueError("Malformed combat movement request")
    actor_id = struct.unpack_from(">q", body)[0]
    path = list(struct.iter_unpack(">iih", body[8:]))
    if len(path) > 6552:
        raise ValueError("Movement path too long")
    return actor_id, path


def apply_client(runtime, owner_id, body, stats_serializer, *, direction):
    if runtime.awaiting_ack is not None:
        raise ValueError("Waiting for previous turn synchronization")
    actor_id, path = decode_request(body)
    fight = runtime.fight
    actor = fight._current_owned(owner_id, actor_id)
    origin = actor.position
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


def apply_ai(runtime, stats_serializer, *, direction):
    """Plan and commit one server movement; attacking remains explicit policy."""
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
