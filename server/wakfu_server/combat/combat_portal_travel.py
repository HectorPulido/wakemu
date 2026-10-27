"""Native byL/byS character travel via the ordinary cpa12161 request.

Gate use is one destination, one MP plus original fei/fek tackle losses.
The original server event producer is unavailable: existing voluntary/area
callbacks remain the explicitly declared Wakemu movement policy.
"""
from copy import deepcopy


def portal_network_pair(entries, exits):
    """byL uses the last Qs.g affiliation; byS uses the first Qs.bdm one.

    Both must agree to produce the native one-point request. Affiliation is
    captured on each gate, never inferred from the moving actor or owner.
    """
    if not entries or not exits:
        return None
    for row in (*entries, *exits):
        if (
            type(row.get("uid")) is not int
            or type(row.get("native_fight_affiliation")) is not int
            or not -128 <= row["native_fight_affiliation"] <= 127
            or row.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
        ):
            raise ValueError("Missing captured native gate affiliation")
    first, last = (
        entries[0]["native_fight_affiliation"],
        entries[-1]["native_fight_affiliation"],
    )
    if (
        first == -1
        or last == -1
        or exits[0]["native_fight_affiliation"] != first
        or exits[-1]["native_fight_affiliation"] != last
    ):
        return None
    return entries[0]["uid"], exits[0]["uid"]


def _gate_actor(fight, owner_id, actor_id, *, server_controlled=False):
    if type(server_controlled) is not bool:
        raise ValueError("Invalid native gate control mode")
    if not server_controlled:
        return fight._current_owned(owner_id, actor_id)
    from .combat_effective_control import effective_server_controlled

    actor = fight.current
    if (
        owner_id is not None
        or actor is None
        or actor.id != actor_id
        or fight.phase != "active"
        or not fight._in_play(actor)
        or not effective_server_controlled(fight, actor)
    ):
        raise ValueError("Invalid server controlled gate movement")
    return actor


def try_apply_portal_travel(
    runtime,
    owner_id,
    actor_id,
    path,
    stats_serializer,
    *,
    runtime_stats_serializer=None,
    step_callback=None,
    server_controlled=False,
):
    """Return a fully prepared gate delivery, or None for ordinary movement.

    All validation, resource payment, QI, callbacks and serialization use an
    unpublished candidate; rejection preserves the original runtime graph.
    """
    if len(path) != 1:
        return None
    rows = getattr(runtime.fight, "native_effect_areas", {})
    if not isinstance(rows, dict) or not any(
        isinstance(row, dict) and row.get("native_type_id") == 19
        for row in rows.values()
    ):
        return None
    candidate = deepcopy(runtime)
    fight = candidate.fight
    actor = _gate_actor(fight, owner_id, actor_id, server_controlled=server_controlled)
    origin, destination = tuple(actor.position), tuple(path[0])
    if origin == destination:
        return None
    from .combat_effect_area_queries import _rows
    from .combat_effect_area_geometry import contains_area_cell

    gates = tuple(row for row in _rows(fight) if row.get("native_type_id") == 19)
    pair = portal_network_pair(
        tuple(row for row in gates if contains_area_cell(row, origin)),
        tuple(row for row in gates if contains_area_cell(row, destination)),
    )
    if pair is None:
        return None
    authority = getattr(fight, "native_rail_movement_authority", None)
    if not callable(authority) or not callable(getattr(authority, "properties", None)):
        raise ValueError("Missing actual native gate movement authority")
    properties = authority.properties(fight, actor)
    if not isinstance(properties, frozenset):
        raise ValueError("Missing native gate movement properties")
    if 105 in properties:
        # byL chooses the ordinary mode: adjacent ordinary walking is still
        # legal; a nonadjacent endpoint will fail the unchanged normal branch.
        return None
    if properties & {3, 88}:
        raise ValueError("Native fighter cannot move through gates")
    from .combat_carrying import carrying_relations

    if carrying_relations(fight, actor)["is_carried"]:
        raise ValueError("Independent carried gate movement is forbidden")
    from .combat_qi_movement import movement_blocked_cells

    blocked = movement_blocked_cells(fight, actor, [destination])
    if blocked is None:
        raise ValueError("Missing actual native gate movement QI")
    if destination not in fight.walkable or destination in blocked:
        raise ValueError("Native gate destination is blocked")
    from .combat_tackle_movement import movement_tackle_cost

    tackle_departures = []
    tackle_ap, tackle_mp = movement_tackle_cost(
        fight, actor, [destination], capture=tackle_departures
    )
    cost = 1 + tackle_mp
    if actor.mp < cost or actor.ap < tackle_ap:
        raise ValueError("Insufficient AP/MP for native gate travel")
    direction = actor.direction
    if type(direction) is not int or not 0 <= direction < 8:
        raise ValueError("Missing native gate movement direction")
    previous = (
        runtime_stats_serializer(actor, fight)
        if runtime_stats_serializer is not None
        else stats_serializer(actor)
    )
    payment = _pay_gate_movement(
        fight, actor, owner_id, tackle_ap, cost, server_controlled=server_controlled
    )
    from .combat_qi_fight import move_registered_actor

    move_registered_actor(fight, actor, destination)
    event = fight._event(
        "movement",
        actor_id=actor_id,
        path=[destination],
        cost=cost,
        on_gates=True,
        gate_entry_uid=pair[0],
        gate_exit_uid=pair[1],
        tackle_ap=tackle_ap,
        tackle_mp=tackle_mp,
    )
    if step_callback is not None:
        from .combat_gate_movement_boundary import (
            POLICY,
            NativeGateMovementBoundary,
            native_gate_movement_scope,
        )

        receipt = NativeGateMovementBoundary(
            POLICY,
            actor_id,
            owner_id,
            fight.turn_id,
            origin,
            destination,
            pair[0],
            pair[1],
            next(
                row["native_fight_affiliation"]
                for row in gates
                if row["uid"] == pair[0]
            ),
            payment["ap_before"],
            payment["mp_before"],
            payment["ap_after"],
            payment["mp_after"],
            tackle_ap,
            tackle_mp,
            actor.native_obstacle_id,
            payment["ap_paid"],
            payment["mp_paid"],
            actor.ap,
            actor.mp,
            payment["ap_raw_post"],
            payment["mp_raw_post"],
        )
        from .combat_equipment_tackle_events import committed_tackle_departure

        with native_gate_movement_scope(fight, receipt):
            with committed_tackle_departure(
                fight, tackle_departures[0] if tackle_departures else None
            ):
                step_callback(fight, actor, origin, destination)
    stats = (
        runtime_stats_serializer(actor, fight)
        if runtime_stats_serializer is not None
        else stats_serializer(actor)
    )
    from .combat_movement import portal_movement
    from .combat_movement_runtime import movement_stats_snapshots
    from .combat_wire import actor_state
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    animation = portal_movement(
        fight.id, candidate.action_id + 1, actor_id, origin, destination, direction
    )
    packets = [animation, candidate._flush()]
    if actor_id not in hidden_snapshot_actor_ids(fight):
        packets.extend(
            (
                12873,
                actor_state(12873, fight.id, actor_id, snapshot),
            )
            for snapshot in movement_stats_snapshots(stats, previous, actor=actor)
        )
    candidate.action_id += 1
    from .combat_area_boundary import adopt_runtime

    adopt_runtime(runtime, candidate)
    return packets, event


def _pay_gate_movement(fight, actor, owner_id, ap, mp, *, server_controlled=False):
    """Preserve Fight.spend setters, recording each actual own raw debit."""
    if (
        _gate_actor(fight, owner_id, actor.id, server_controlled=server_controlled)
        is not actor
    ):
        raise ValueError("Gate payment actor differs from actual participant")
    if (
        type(ap) is not int
        or type(mp) is not int
        or min(ap, mp) < 0
        or actor.ap < ap
        or actor.mp < mp
    ):
        raise ValueError("Insufficient or invalid action resources")
    from .combat_movement_payment_events import _raw_resources

    if getattr(actor, "effect_resource_raw_currents", None) is not None:
        from .combat_resource_pa_notifications import (
            shift_resource_current,
            resource_raw_current,
        )

        ap_before = resource_raw_current(actor, 2)
        # Fight.spend deliberately invokes the AP setter even for zero AP.
        shift_resource_current(fight, actor, 2, ap, subtract=True)
        ap_after = resource_raw_current(actor, 2)
        # AP notifications may change MP before its own actual payment setter.
        mp_before = resource_raw_current(actor, 3)
        shift_resource_current(fight, actor, 3, mp, subtract=True)
        mp_after = resource_raw_current(actor, 3)
    else:
        ap_before = actor.ap
        actor.ap -= ap
        if actor.effect_stats is not None and 2 in actor.effect_stats:
            actor.effect_stats[2] = actor.ap
        from .combat_resource_pa_notifications import notify_resource_pa

        notify_resource_pa(fight, actor, 2, before_current=ap_before)
        ap_after = actor.ap
        mp_before = actor.mp
        actor.mp -= mp
        mp_after = actor.mp
    fight._sync_resources(actor)
    ap_raw_post, mp_raw_post = _raw_resources(actor)
    return dict(
        ap_before=ap_before,
        ap_after=ap_after,
        mp_before=mp_before,
        mp_after=mp_after,
        ap_paid=ap_before - ap_after,
        mp_paid=mp_before - mp_after,
        ap_raw_post=ap_raw_post,
        mp_raw_post=mp_raw_post,
    )
