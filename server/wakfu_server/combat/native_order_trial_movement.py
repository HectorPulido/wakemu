"""Reviewed server consumer of real eVY328 orders for the order arcade.

The installed client actor consumer is empty. This opt-in policy spends native
MP on its pinned reviewed lane, then ends the turn. The native cell is a
command anchor, not a claim about an unrecovered destination algorithm.
Operand3 remains an order operand; it is never a movement distance or AI flag.
"""
POLICY = {
    "schema": "reviewed-native-order-movement-v1",
    "authority": "wakemu_reconstructed_server_consumer_not_installed_client_ai",
    "source_effect": 120675,
    "source_state": 3127,
    "movement": "pinned_reviewed_lane_with_native_mp_and_registered_edges",
    "turn_end": "normal_automatic_native_boundary",
}


def eligible(fight, actor):
    if getattr(fight, "native_order_trial", None) is None:
        return False
    selected = getattr(fight, "native_order_movement_policy", None)
    if selected is None:
        return False
    if selected != POLICY:
        raise ValueError("Order movement lacks its frozen server policy")
    if (
        actor is None
        or fight.phase != "active"
        or fight.current is not actor
        or fight.actors.get(actor.id) is not actor
        or actor.controlled
        or not fight._in_play(actor)
    ):
        return False
    from .native_order_trial_checkpoint import validate
    from .native_order_trial_events import _owned_summon

    proof, _, _ = validate(
        fight.native_order_trial, encounter_id=fight.id, replay=False
    )
    if actor.id == proof.owner_id:
        return False
    _owned_summon(fight, actor, proof.owner_id)
    return any(
        entry.reference == 3127 and entry.level > 0
        for entry in actor.state_ledger.entries
    )


def record(handler, effect, invocation, *, runner_uid, cell, value):
    fight = handler.fight
    if (
        getattr(fight, "native_order_trial", None) is None
        or getattr(fight, "native_order_movement_policy", None) is None
        or invocation.reference != 120675
    ):
        return None
    from .combat_native_order_hooks import NativeOrderHookHandler, NativeOrderCell
    from .combat_native_container import resolve_state_container

    actor = fight.actors.get(invocation.target_id)
    if actor is not fight.current:
        return None  # Native birth/other-turn notifications are not turn commands.
    if (
        type(handler) is not NativeOrderHookHandler
        or effect.get("effect_class") != 328
        or not isinstance(cell, NativeOrderCell)
        or type(runner_uid) is not int
        or runner_uid <= 0
        or value != 3
        or type(invocation.state_uid) is not int
        or invocation.state_uid <= 0
        or actor is None
        or invocation.caster_id != actor.id
        or not eligible(fight, actor)
    ):
        raise ValueError("Order movement requires its actual native328 result")
    parent = resolve_state_container(fight, invocation.state_uid)
    if parent is None or parent.reference != 3127 or parent.target_id != actor.id:
        raise ValueError("Order movement has no original3127 carrier")
    anchor = (cell.x, cell.y, cell.z)
    if anchor not in fight.walkable:
        raise ValueError("Native order anchor is outside the actual arcade")
    row = dict(
        actor_id=actor.id,
        turn_id=fight.turn_id,
        carrier_uid=parent.uid,
        runner_uid=runner_uid,
        effect_reference=120675,
        operand=value,
        anchor=list(anchor),
        consumed=False,
    )
    commands = getattr(fight, "native_order_commands", {})
    if not isinstance(commands, dict):
        raise ValueError("Invalid native order command ledger")
    fight.native_order_commands = dict(commands, **{str(actor.id): row})
    fight._event("native_order_command", **row)
    return row


def _validate_command(fight, actor, command):
    if (
        not isinstance(command, dict)
        or command.get("actor_id") != actor.id
        or type(command.get("turn_id")) is not int
        or not 0 < command["turn_id"] <= fight.turn_id
        or command.get("effect_reference") != 120675
        or command.get("operand") != 3
        or type(command.get("runner_uid")) is not int
        or command["runner_uid"] <= 0
        or type(command.get("consumed")) is not bool
    ):
        raise ValueError("Stale or foreign native order command")
    if not any(
        entry.uid == command.get("carrier_uid") and entry.reference == 3127
        for entry in actor.state_ledger.entries
    ):
        raise ValueError("Native order carrier expired before movement")
    anchor = command.get("anchor")
    if (
        not isinstance(anchor, list)
        or len(anchor) != 3
        or any(type(value) is not int for value in anchor)
        or tuple(anchor) not in fight.walkable
    ):
        raise ValueError("Order movement lost its actual native cell anchor")


def path_for(fight, actor, command):
    if not eligible(fight, actor):
        raise ValueError("Order movement has no current native turn authority")
    _validate_command(fight, actor, command)
    if command["turn_id"] != fight.turn_id or command["consumed"]:
        raise ValueError("Stale or foreign native order command")
    lane = getattr(fight, "native_order_lane", None)
    from .native_order_trial_checkpoint import validate

    proof, _, _ = validate(
        fight.native_order_trial, encounter_id=fight.id, replay=False
    )
    if (
        not isinstance(lane, dict)
        or lane.get("schema") != "reviewed-native-order-lane-v1"
        or lane.get("mode") != proof.mode
        or not lane.get("authority")
        or type(lane.get("geometry_sha256")) is not str
        or len(lane["geometry_sha256"]) != 64
        or not isinstance(lane.get("track"), list)
        or len(lane["track"]) < 2
    ):
        raise ValueError("Order movement lost its pinned reviewed lane")
    track = tuple(tuple(cell) for cell in lane["track"])
    if (
        len(set(track)) != len(track)
        or fight.edges is None
        or any(cell not in fight.walkable for cell in track)
        or any(
            (before, after) not in fight.edges
            for before, after in zip(track, track[1:])
        )
    ):
        raise ValueError("Order lane is not an actual directed native floor path")
    if actor.mp <= 0 or actor.position not in track:
        return ()
    proposed = track[track.index(actor.position) + 1 :][: actor.mp]
    from .combat_qi_movement import movement_blocked_cells

    blocked = movement_blocked_cells(fight, actor, proposed)
    if blocked is None:
        raise ValueError("Order movement requires registered native QI authority")
    path = []
    for cell in proposed:
        if cell in blocked:
            break
        path.append(cell)
    path = tuple(path)
    from .combat_rail_movement import movement_cost
    from .combat_tackle_movement import movement_tackle_cost

    while path:
        cost, _ = movement_cost(fight, actor, path)
        tackle_ap, tackle_mp = movement_tackle_cost(fight, actor, path)
        if cost + tackle_mp <= actor.mp and tackle_ap <= actor.ap:
            return path
        path = path[:-1]
    return ()


def move_current(runtime, *, area_provider=None, _step_callback=None, _result=None):
    fight, actor = runtime.fight, runtime.fight.current
    if not eligible(fight, actor):
        return []
    if area_provider is not None:
        from .combat_movement_runtime import _with_areas

        def operation(candidate, callback):
            result = {"event": {"path": ()}}
            packets = move_current(candidate, _step_callback=callback, _result=result)
            return packets, result

        packets, _ = _with_areas(runtime, area_provider, operation)
        return packets
    command = getattr(fight, "native_order_commands", {}).get(str(actor.id))
    if command is None:
        return []
    _validate_command(fight, actor, command)
    if command["consumed"] or command["turn_id"] < fight.turn_id:
        return []  # An old notification never fabricates a fresh turn command.
    path = path_for(fight, actor, command)
    command["consumed"] = True
    if not path:
        return []
    if _step_callback is None:
        raise ValueError("Order movement requires original area step callbacks")
    from .combat_movement import movement
    from .combat_movement_runtime import direction_after_path, movement_stats_snapshots
    from .combat_carrying import set_registered_direction
    from .combat_wire import actor_state

    serialize = runtime.runtime_stats_serializer
    if not callable(serialize):
        raise ValueError("Order movement requires actual native actor serialization")
    before, baseline = actor.position, serialize(actor, fight)
    event = fight._move_actor(actor, path, step_callback=_step_callback)
    if _result is not None:
        _result["event"] = event
    actual = event["path"]
    direction = direction_after_path(before, actual, actor.direction)
    in_play = fight._in_play(actor)
    if in_play:
        set_registered_direction(fight, actor, direction)
    runtime.action_id += 1
    packets = [
        movement(
            fight.id,
            runtime.action_id,
            actor.id,
            [before, *actual],
            direction,
            on_rails=event.get("on_rails") is True,
        )
    ]
    packets.append(runtime._flush())
    if in_play and fight.phase == "active":
        packets.extend(
            (12873, actor_state(12873, fight.id, actor.id, snapshot))
            for snapshot in movement_stats_snapshots(
                serialize(actor, fight), baseline, actor=actor
            )
        )
    return packets


def area_provider(runtime):
    """Use the standard shared runtime's frozen character/deck authority."""
    from .combat_expiration_provider import OwnedExpirationFactory
    from .combat_area_transaction import prepare_area_movement

    factory = runtime.expiration_runtime_factory
    if (
        type(factory) is not OwnedExpirationFactory
        or factory.area_callbacks is not True
    ):
        raise ValueError("Order movement requires its normal owned area runtime")

    def prepare(fight, **boundary):
        source = factory.characters[factory.actor_id]
        return prepare_area_movement(
            source,
            factory.monsters,
            fight,
            factory.decks[factory.actor_id],
            player_characters=factory.characters,
            deck_blobs=factory.decks,
            **boundary
        )

    return prepare
