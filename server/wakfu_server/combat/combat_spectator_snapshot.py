"""Build a spectator bootstrap from an authoritative shared fight snapshot.

This module does not create an actor, join participant membership, or execute
an effect. Unsupported retained effect families fail closed rather than
producing a visibly incomplete active-fight snapshot.
"""
from .combat_environment_glyphs import environment_sections
from .combat_spectator_wire import spectator_bootstrap, timeline_snapshot
from .combat_turns import initial_order
from .combat_wire import initial_timeline, topology


def _retained_carrier_packets(fight, action_id):
    """Reinstall tracked retained effects without re-running child effects."""
    if fight.native_retained_tracking is not True:
        raise ValueError("Spectator snapshot needs a complete retained-effect ledger")
    if not isinstance(fight.native_retained_records, dict) or not isinstance(
        fight.native_retained_order, list
    ):
        raise ValueError("Spectator snapshot has no retained-effect ordering")

    from .combat_pending_state import pending_state_uids
    from .combat_retained_effects import NativeRetainedEffectView, RetainedEffect
    from .combat_state_managers import state_managers

    live = (
        set(fight.owned_stat_effects)
        | set(fight.state_wire_payloads)
        | set(fight.native_owned_group_effects)
        | set(getattr(fight, "native_owned_area_effects", {}))
    )
    live.update(
        entry.uid
        for actor in state_managers(fight)
        for entry in actor.state_ledger.entries
    )
    pending = pending_state_uids(fight)
    if (
        pending
        or live != set(fight.native_retained_records)
        or live != set(fight.native_retained_order)
    ):
        raise ValueError("Spectator snapshot has an incomplete retained-effect view")
    if len(fight.native_retained_order) != len(set(fight.native_retained_order)):
        raise ValueError("Spectator snapshot has duplicate retained-effect order")

    view = NativeRetainedEffectView(
        fight,
        [
            RetainedEffect(**fight.native_retained_records[uid])
            for uid in fight.native_retained_order
        ],
        population_verified_complete=True,
    )
    from .combat_state_carrier import state_carrier_application
    from .combat_stat_effects import owned_effect_delivery

    packets = []
    for entry in view.entries:
        uid = entry.uid
        sources = []
        if uid in fight.state_wire_payloads:
            sources.append(fight.state_wire_payloads[uid])
        if uid in fight.owned_stat_effects:
            sources.append(fight.owned_stat_effects[uid].get("payload"))
        if uid in getattr(fight, "native_owned_area_effects", {}):
            sources.append(fight.native_owned_area_effects[uid].get("payload"))
        if uid in fight.native_owned_group_effects:
            sources.append(fight.native_owned_group_effects[uid].get("payload"))
        if len(sources) != 1 or not isinstance(sources[0], str):
            raise ValueError("Retained effect has no unique current wire payload")
        payload = bytes.fromhex(sources[0])
        manager_id = entry.manager_id
        target_id = entry.target_id if entry.target_id is not None else manager_id
        if type(manager_id) is not int or manager_id == 0 or type(target_id) is not int:
            raise ValueError("Retained effect has no current native manager")
        if entry.effect_class == 310:
            opcode, body = 12613, state_carrier_application(
                fight.id,
                action_id,
                uid=uid,
                target_id=target_id,
                running_effect_payload=payload,
            )
        else:
            # cvX/12613 retains the already evaluated running carrier with its
            # execution flag cleared. This preserves the effect manager and
            # current owned payload without rerunning gameplay children.
            opcode, body = owned_effect_delivery(
                fight.id,
                action_id,
                native_opcode=12613,
                effect_class=entry.effect_class,
                target_id=target_id,
                uid=uid,
                running_effect_payload=payload,
            )
        if manager_id != target_id:
            # The protobuf's original target remains part of the exact payload;
            # the frame owner is the actor whose native manager contains the UID.
            import struct

            body = body[:-16] + struct.pack(">qq", manager_id, uid)
        packets.append((opcode, body))
    return tuple(packets)


def current_snapshot(fight, shared, *, actor_payload, deadline_ms=None):
    """Return a native cva bootstrap and safe current retained state packets.

    `actor_payload(fight, actor)` must produce the same authoritative `(stats,
    effects)` pair used for current join bootstrap. During an active fight,
    `deadline_ms` is required and `myG` is reconstructed from the live FSM,
    never reused from placement.
    """
    if not callable(actor_payload):
        raise ValueError("Authoritative native actor serializer is required")
    if getattr(shared, "is_duel", False):
        raise ValueError("Private duel snapshots are not publicly observable")
    context = getattr(shared, "join_context", None)
    if not isinstance(context, dict):
        raise ValueError("Live fight has no native spectator context")
    required = {
        "arena",
        "terrain_effect_id",
        "terrain_instance_id",
        "leaders",
    }
    if required - context.keys():
        raise ValueError("Live fight native spectator context is incomplete")
    arena = context["arena"]
    if (
        not isinstance(arena, dict)
        or arena.get("map_id") != shared.map_id
        # Arena instance is a native topology identity, not the world instance.
        # The registry authorizes the observer against shared.map_id/instance_id.
        or type(arena.get("instance_id")) is not int
        or type(fight.id) is not int
        or fight.id <= 0
        or type(shared.map_id) is not int
        or shared.map_id <= 0
        or type(shared.instance_id) is not int
        or shared.instance_id < 0
    ):
        raise ValueError("Live fight context differs from its shared location")
    leaders = context["leaders"]
    if set(leaders) != {0, 1} or any(
        identity not in fight.actors or fight.actors[identity].team != team
        for team, identity in leaders.items()
    ):
        raise ValueError("Live fight leaders are not current actors")

    actors = list(fight.actors.values())
    if not actors or len(actors) > 127:
        raise ValueError("Unsupported live spectator roster size")
    participants = []
    for actor in actors:
        stats, effects = actor_payload(fight, actor)
        if not isinstance(stats, bytes) or not isinstance(effects, bytes):
            raise ValueError("Native actor serializer returned invalid payloads")
        participants.append(
            dict(
                actor_id=actor.id,
                myB=0 if actor.controlled else 1,
                myn=actor.team,
                myC=1,
                myE=stats,
                myF=effects,
            )
        )

    if fight.phase == "placement":
        phase_code = 1  # Native fbZ.PLACEMENT.
        order = initial_order(
            fight.id,
            [
                dict(
                    id=actor.id,
                    team=actor.team,
                    initiative=actor.initiative,
                    effective_level=actor.effective_level,
                )
                for actor in actors
            ],
        )
        fight_timeline = initial_timeline([actor.id for actor in actors], order)
        action_id = 0
    elif fight.phase == "active":
        if type(deadline_ms) is not int or deadline_ms <= 0:
            raise ValueError("Active spectator snapshot requires current deadline")
        from .combat_recovery import timeline

        phase_code = 2  # Native fbZ.ACTION.
        fight_timeline = timeline(fight, deadline_ms=deadline_ms)
        # Use the last committed native delivery boundary. Allocating a new
        # ID here would mutate the participant stream solely for a spectator.
        action_id = getattr(shared.runtime, "native_action_id", 0)
        if fight.state_wire_payloads and (type(action_id) is not int or action_id <= 0):
            raise ValueError("State snapshot has no current native action sequence")
    else:
        raise ValueError("Only live placement or action fights can be observed")

    value = dict(
        fight_id=fight.id,
        kind=2,
        bqh=arena["map_id"],
        myo=context["terrain_effect_id"],
        myp=context["terrain_instance_id"],
        myD=topology(arena),
        myG=fight_timeline,
        myI=leaders[0],
        myJ=leaders[1],
        compact=False,
        participants=participants,
        myH=[],
        myM=[],
        myN=[],
        myK=environment_sections(fight),
    )
    timeline_state = timeline_snapshot(3)
    bootstrap_packet = spectator_bootstrap(
        value, phase_code=phase_code, timeline_snapshot=timeline_state
    )
    state_packets = (
        _retained_carrier_packets(fight, action_id) if fight.phase == "active" else ()
    )
    return (bootstrap_packet, *state_packets)
