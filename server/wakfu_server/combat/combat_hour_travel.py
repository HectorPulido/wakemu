"""Native byL/byW owned-hour travel through the ordinary cpa12161 request.

byL selects XELOR before gate mode; byW requires positive WP and owned HOUR
coverage at both endpoints. dbe charges one WP plus fei tackle AP/MP. Native
TELEPORT presentation and voluntary1005 callbacks are explicit Wakemu policy;
the original server publisher is unavailable.
"""
from contextlib import contextmanager
from copy import deepcopy

NATIVE_XELOR_BREED = 5  # Original eGE.pIv: XELOR reference5, not enum ordinal6.
POLICY = "wakemu.native-hour-movement-boundary-v1"
_SCOPE = "_wakemu_native_hour_movement_boundary"


def hour_pair(fight, actor_id, origin, destination):
    from .combat_effect_area_geometry import contains_area_cell

    rows = getattr(fight, "native_effect_areas", {})
    if not isinstance(rows, dict):
        raise ValueError("Missing actual native hour population")
    if hasattr(fight, "native_global_pv_collections"):
        from .combat_global_pv_collections import global_area_order

        order = global_area_order(fight)
    else:
        order = tuple(rows)
    hours = []
    for identity in order:
        row = rows[identity]
        if not isinstance(row, dict):
            raise ValueError("Invalid actual native hour population")
        if row.get("native_hour_contract") is not True:
            continue
        if (
            row.get("uid") != identity
            or row.get("native_area_contract") != "faZ"
            or row.get("native_type_id") != 1
        ):
            raise ValueError("Invalid actual native HOUR identity")
        if row.get("owner_id") == actor_id:
            hours.append(row)
    # This is a read-only Qs query. Generic _rows also refreshes anchored faN
    # geometry and must not mutate unrelated areas on a rejected request.
    entries = tuple(row for row in hours if contains_area_cell(row, origin))
    exits = tuple(row for row in hours if contains_area_cell(row, destination))
    if not entries or not exits:
        return None
    return entries[0]["uid"], exits[0]["uid"]


def validate_hour_boundary_facts(facts):
    if (
        not isinstance(facts, dict)
        or set(facts)
        != {
            "policy",
            "actor_id",
            "owner_id",
            "turn_id",
            "from_cell",
            "to_cell",
            "entry_uid",
            "exit_uid",
            "obstacle_id",
        }
        or facts["policy"] != POLICY
        or any(
            type(facts[key]) is not int
            for key in (
                "actor_id",
                "owner_id",
                "turn_id",
                "entry_uid",
                "exit_uid",
                "obstacle_id",
            )
        )
        or facts["actor_id"] == 0
        or any(not 0 < facts[key] < (1 << 63) for key in ("entry_uid", "exit_uid"))
        or not -1 <= facts["obstacle_id"] <= 126
        or any(
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            for cell in (facts["from_cell"], facts["to_cell"])
        )
        or tuple(facts["from_cell"]) == tuple(facts["to_cell"])
    ):
        raise ValueError("Invalid native hour movement receipt")
    return facts


def current_hour_movement_boundary(fight, actor_id, origin, destination):
    facts = getattr(fight, _SCOPE, None)
    if facts is None:
        return None
    validate_hour_boundary_facts(facts)
    actor = fight._current_owned(facts["owner_id"], actor_id)
    from .combat_qi_fight import current_registry

    slot_id = facts["obstacle_id"]
    slot = current_registry(fight).slots[slot_id] if slot_id >= 0 else None
    if (
        facts["actor_id"] != actor_id
        or facts["turn_id"] != fight.turn_id
        or tuple(facts["from_cell"]) != tuple(origin)
        or tuple(facts["to_cell"]) != tuple(destination)
        or tuple(actor.position) != tuple(destination)
        or actor.native_obstacle_id != slot_id
        or slot is None
        or slot["identity"] != ["actor", actor_id]
        or tuple(slot["position"]) != tuple(destination[:2])
    ):
        raise ValueError("Native hour receipt differs from committed movement")
    # Payment and live area coverage are checked before callbacks. A valid
    # subscribed effect may then move the hand or retire a dial.
    return facts


@contextmanager
def _hour_scope(fight, actor, owner_id, origin, destination, pair, payment):
    if getattr(fight, _SCOPE, None) is not None:
        raise ValueError("Nested native hour movement publication")
    if hour_pair(fight, actor.id, origin, destination) != pair:
        raise ValueError("Native hour movement pair changed before publication")
    facts = dict(
        policy=POLICY,
        actor_id=actor.id,
        owner_id=owner_id,
        turn_id=fight.turn_id,
        from_cell=origin,
        to_cell=destination,
        entry_uid=pair[0],
        exit_uid=pair[1],
        obstacle_id=actor.native_obstacle_id,
    )
    setattr(fight, _SCOPE, facts)
    try:
        current_hour_movement_boundary(fight, actor.id, origin, destination)
        from .combat_movement_payment_events import committed_step_payment

        with committed_step_payment(
            fight,
            actor,
            origin=origin,
            destination=destination,
            index=0,
            **{
                key: payment[key]
                for key in (
                    "ap_before",
                    "ap_after",
                    "mp_before",
                    "mp_after",
                    "ap_paid",
                    "mp_paid",
                    "wp_before",
                    "wp_after",
                    "wp_paid",
                )
            },
        ):
            yield
    finally:
        delattr(fight, _SCOPE)


def try_apply_hour_travel(
    runtime,
    owner_id,
    actor_id,
    path,
    stats_serializer,
    *,
    runtime_stats_serializer=None,
    step_callback=None
):
    if len(path) != 1:
        return None
    rows = getattr(runtime.fight, "native_effect_areas", {})
    if not isinstance(rows, dict) or not any(
        isinstance(row, dict) and row.get("native_hour_contract") is True
        for row in rows.values()
    ):
        return None
    actor = runtime.fight._current_owned(owner_id, actor_id)
    origin, destination = tuple(actor.position), tuple(path[0])
    if origin == destination:
        return None
    pair = hour_pair(runtime.fight, actor_id, origin, destination)
    if pair is None:
        return None
    authority = getattr(runtime.fight, "native_rail_movement_authority", None)
    if not callable(authority) or not callable(getattr(authority, "properties", None)):
        raise ValueError("Missing actual native hour movement authority")
    from .combat_runtime_adapter import NativeActorAuthority

    metadata = authority(runtime.fight, actor)
    if not isinstance(metadata, NativeActorAuthority):
        raise ValueError("Missing actual native hour movement breed identity")
    if metadata.breed_id != NATIVE_XELOR_BREED:
        return None  # Original byL does not select WITH_XELORS_DIAL.
    wp = (actor.effect_stats or {}).get(4)
    if type(wp) is not int:
        raise ValueError("Missing actual native hour movement WP")
    if wp <= 0:
        return None  # byL can still select a gate or ordinary walking.
    if step_callback is None:
        raise ValueError("Native hour travel requires its payment and area callbacks")
    properties = authority.properties(runtime.fight, actor)
    if not isinstance(properties, frozenset):
        raise ValueError("Missing native hour movement properties")
    if properties & {3, 88}:  # dbe rejects these before any byK selection.
        raise ValueError("Native fighter cannot move between hours")
    from .combat_carrying import carrying_relations

    if carrying_relations(runtime.fight, actor)["is_carried"]:
        raise ValueError("Independent carried hour movement is forbidden")
    from .combat_qi_movement import movement_blocked_cells

    blocked = movement_blocked_cells(runtime.fight, actor, [destination])
    if blocked is None:
        raise ValueError("Missing actual native hour movement QI")
    if destination not in runtime.fight.walkable or destination in blocked:
        raise ValueError("Native hour destination is blocked")
    from .combat_tackle_movement import movement_tackle_cost

    tackle_departures = []
    tackle_ap, tackle_mp = movement_tackle_cost(
        runtime.fight, actor, [destination], capture=tackle_departures
    )
    if actor.ap < tackle_ap or actor.mp < tackle_mp:
        raise ValueError("Insufficient AP/MP for native hour disengagement")
    direction = actor.direction
    if type(direction) is not int or not 0 <= direction < 8:
        raise ValueError("Missing native hour movement direction")
    candidate = deepcopy(runtime)
    fight = candidate.fight
    actor = fight._current_owned(owner_id, actor_id)
    previous = (
        runtime_stats_serializer(actor, fight)
        if runtime_stats_serializer is not None
        else stats_serializer(actor)
    )
    actor.effect_stats[4] = wp - 1
    # Reuse only the already-qualified AP/MP PA setter sequence, not any gate
    # geometry, costs, properties, callbacks or presentation policy.
    from .combat_portal_travel import _pay_gate_movement

    payment = _pay_gate_movement(fight, actor, owner_id, tackle_ap, tackle_mp)
    payment.update(wp_before=wp, wp_after=wp - 1, wp_paid=1)
    from .combat_qi_fight import move_registered_actor

    move_registered_actor(fight, actor, destination)
    event = fight._event(
        "movement",
        actor_id=actor_id,
        path=[destination],
        cost=tackle_mp,
        wp_cost=1,
        on_hours=True,
        hour_entry_uid=pair[0],
        hour_exit_uid=pair[1],
        tackle_ap=tackle_ap,
        tackle_mp=tackle_mp,
    )
    if step_callback is not None:
        from .combat_equipment_tackle_events import committed_tackle_departure

        with _hour_scope(fight, actor, owner_id, origin, destination, pair, payment):
            with committed_tackle_departure(
                fight, tackle_departures[0] if tackle_departures else None
            ):
                step_callback(fight, actor, origin, destination)
    stats = (
        runtime_stats_serializer(actor, fight)
        if runtime_stats_serializer is not None
        else stats_serializer(actor)
    )
    from .combat_movement import hour_movement
    from .combat_movement_runtime import movement_stats_snapshots
    from .combat_wire import actor_state
    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    packets = [
        hour_movement(
            fight.id, candidate.action_id + 1, actor_id, origin, destination, direction
        ),
        candidate._flush(),
    ]
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
