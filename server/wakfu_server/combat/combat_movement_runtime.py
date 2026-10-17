"""Client 12161 movement through authoritative FSM and native animation.

Serializer callback receives the updated actor and must serialize its owned
fight data. No captured stats are accepted implicitly.
"""
import struct
from .combat_movement import movement
from .combat_wire import actor_state


def movement_stats_snapshot(stats, previous=None, *, position_owned=True):
    """An existing movement action owns position; follow it with exact PCs only."""
    if isinstance(stats, bytes) and stats and stats[0] in (2, 3):
        from .combat_characteristic_snapshot import characteristics_only_snapshot

        projected = characteristics_only_snapshot(stats)
        if isinstance(previous, bytes) and previous and previous[0] in (2, 3):

            def metadata(payload):
                # Keep every non-position/non-PC field, including QI/control/book.
                position = 1 + (8 if payload[0] == 3 else 0)
                table = position + 30
                characteristics_only_snapshot(payload)  # Validate before slicing.
                count = struct.unpack_from(">H", payload, table)[0]
                end = table + 2 + count * 17
                suffix = payload[end:]
                if payload[0] == 3:
                    # Player snapshots repeat PCs after AI control and breed.
                    public_table = end + 4
                    if len(payload) < public_table + 2:
                        raise ValueError(
                            "Truncated native player public characteristics"
                        )
                    public_count = struct.unpack_from(">H", payload, public_table)[0]
                    public_end = public_table + 2 + public_count * 17
                    if public_end > len(payload):
                        raise ValueError(
                            "Truncated native player public characteristics"
                        )
                    suffix = payload[end:public_table] + payload[public_end:]
                spatial = b"" if position_owned else payload[position : position + 20]
                return (
                    payload[:position]
                    + spatial
                    + payload[position + 20 : table]
                    + suffix
                )

            if metadata(stats) != metadata(previous):
                return stats
        return projected
    # Preserve custom serializer adapters and already partial native snapshots.
    return stats


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


def apply_client(
    runtime,
    owner_id,
    body,
    stats_serializer,
    *,
    area_provider=None,
    runtime_stats_serializer=None,
    _step_callback=None,
):
    if runtime_stats_serializer is not None and not callable(runtime_stats_serializer):
        raise ValueError("Invalid current-fight movement stats serializer")
    if area_provider is not None:
        return _with_areas(
            runtime,
            area_provider,
            lambda candidate, callback: apply_client(
                candidate,
                owner_id,
                body,
                stats_serializer,
                runtime_stats_serializer=runtime_stats_serializer,
                _step_callback=callback,
            ),
        )
    if runtime.awaiting_ack is not None:
        raise ValueError("Waiting for previous turn synchronization")
    actor_id, path = decode_request(body)
    fight = runtime.fight
    actor = fight._current_owned(owner_id, actor_id)
    from .combat_portal_travel import try_apply_portal_travel

    gate = try_apply_portal_travel(
        runtime,
        owner_id,
        actor_id,
        path,
        stats_serializer,
        runtime_stats_serializer=runtime_stats_serializer,
        step_callback=_step_callback,
    )
    if gate is not None:
        return gate
    origin = actor.position
    direction = direction_after_path(origin, path, getattr(actor, "direction", None))
    # Serialize anticipated owned state before committing, so codec failure
    # cannot spend MP or strand the actor. The FSM still validates every edge.
    import copy

    from .combat_carrying import set_registered_direction

    if _step_callback is not None:
        previous_stats = (
            runtime_stats_serializer(actor, fight)
            if runtime_stats_serializer is not None
            else stats_serializer(actor)
        )
        event = fight.move(owner_id, actor_id, path, step_callback=_step_callback)
        path = event["path"]
        direction = direction_after_path(
            origin, path, getattr(actor, "direction", None)
        )
        set_registered_direction(fight, actor, direction)
        stats = (
            runtime_stats_serializer(actor, fight)
            if runtime_stats_serializer is not None
            else stats_serializer(actor)
        )
    else:
        previous_stats = None
        candidate_fight = copy.deepcopy(fight)
        candidate = candidate_fight.actors[actor_id]
        candidate_fight.move(owner_id, actor_id, path)
        set_registered_direction(candidate_fight, candidate, direction)
        stats = (
            runtime_stats_serializer(candidate, candidate_fight)
            if runtime_stats_serializer is not None
            else stats_serializer(candidate)
        )
    animation = movement(
        fight.id, runtime.action_id + 1, actor_id, [origin, *path], direction
    )
    refresh = (
        12873,
        actor_state(
            12873, fight.id, actor_id, movement_stats_snapshot(stats, previous_stats)
        ),
    )
    if _step_callback is None:
        event = fight.move(owner_id, actor_id, path)
        set_registered_direction(fight, actor, direction)
    runtime.action_id += 1
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    final = [] if actor_id in hidden_snapshot_actor_ids(fight) else [refresh]
    return [animation, runtime._flush(), *final], event


def apply_ai(
    runtime, stats_serializer, *, direction, area_provider=None, _step_callback=None
):
    """Plan and commit one server movement; attacking remains explicit policy."""
    if area_provider is not None:
        return _with_areas(
            runtime,
            area_provider,
            lambda candidate, callback: apply_ai(
                candidate,
                stats_serializer,
                direction=direction,
                _step_callback=callback,
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
    from .combat_carrying import set_registered_direction

    origin = actor.position
    if _step_callback is not None:
        previous_stats = stats_serializer(actor)
        result["event"] = fight.server_move(
            actor.id, path, step_callback=_step_callback
        )
        path = result["event"]["path"]
        result["path"] = path
        direction = direction_after_path(origin, path, actor.direction)
        set_registered_direction(fight, actor, direction)
        stats = stats_serializer(actor)
    else:
        previous_stats = None
        candidate_fight = copy.deepcopy(fight)
        candidate = candidate_fight.actors[actor.id]
        candidate_fight.server_move(actor.id, path)
        set_registered_direction(candidate_fight, candidate, direction)
        stats = stats_serializer(candidate)
    animation = movement(
        fight.id, runtime.action_id + 1, actor.id, [origin, *path], direction
    )
    refresh = (
        12873,
        actor_state(
            12873, fight.id, actor.id, movement_stats_snapshot(stats, previous_stats)
        ),
    )
    if _step_callback is None:
        result["event"] = fight.server_move(actor.id, path)
        set_registered_direction(fight, actor, direction)
    runtime.action_id += 1
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    final = [] if actor.id in hidden_snapshot_actor_ids(fight) else [refresh]
    return [animation, runtime._flush(), *final], result


def _with_areas(runtime, provider, operation):
    from copy import deepcopy
    from .combat_area_boundary import adopt_fight, adopt_runtime
    from .combat_characteristic_reconciliation import characteristic_signatures

    candidate = deepcopy(runtime)
    before_callbacks = characteristic_signatures(candidate.fight)
    callbacks = []
    action_id = candidate.action_id + 2

    def deliver_step(fight, actor, before, cell):
        preview, packets = provider(
            fight,
            actor_id=actor.id,
            action_id=action_id,
            path=[cell],
            origin=before,
        )
        # execute_steps holds the current actor object between resource checks.
        adopt_fight(fight, preview)
        callbacks.extend(packets)

    packets, result = operation(candidate, deliver_step)
    event = result.get("event", result)
    if event.get("path"):
        candidate.action_id += 1
        packets = list(packets)
        from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

        hidden = hidden_snapshot_actor_ids(candidate.fight)
        packets = [
            (opcode, payload)
            for opcode, payload in packets
            if opcode != 12873 or struct.unpack_from(">q", payload, 4)[0] not in hidden
        ]
        refreshes = [packet for packet in packets if packet[0] == 12873]
        refreshed = {
            struct.unpack_from(">q", payload, 4)[0] for _, payload in refreshes
        }
        changed_stats = candidate._changed_stat_packets(
            before_callbacks, exclude=refreshed
        )
        from .combat_wire import decode_actor_state

        projected_changes = []
        for opcode, payload in changed_stats:
            state = decode_actor_state(opcode, payload)
            identity = state["actor_id"]
            previous = runtime.fight.actors.get(identity)
            actor = candidate.fight.actors[identity]
            stats = state["state"]
            if previous is not None and previous.position == actor.position:
                serialize = runtime.runtime_stats_serializer
                baseline = (
                    serialize(previous, runtime.fight)
                    if serialize is not None
                    else runtime.stats_serializer(previous)
                )
                stats = movement_stats_snapshot(stats, baseline, position_owned=False)
            projected_changes.append(
                (opcode, actor_state(opcode, candidate.fight.id, identity, stats))
            )
        changed_stats = projected_changes
        if callbacks:
            # These snapshots already include every step callback's mutation.
            # Native cvX completion also applies evaluated resource deltas,
            # including its retained/execute-false branch. Queue the final
            # cuU snapshots after those effects or the client applies a delta
            # twice relative to the authoritative final current/max values.
            packets = [packet for packet in packets if packet[0] != 12873]
            packets.extend(callbacks)
            packets.extend(refreshes)
        if callbacks or changed_stats:
            packets.extend(changed_stats)
            packets.append(candidate._flush())
    adopt_runtime(runtime, candidate)
    return packets, result
