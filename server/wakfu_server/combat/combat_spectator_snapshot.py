"""Build a spectator bootstrap from an authoritative shared fight snapshot.

This module does not create an actor, join participant membership, or execute
an effect. Unsupported retained effect families fail closed rather than
producing a visibly incomplete active-fight snapshot.
"""
from .combat_environment_glyphs import environment_sections
from .combat_live_area_snapshot import sections as live_area_sections
from .combat_spectator_wire import spectator_bootstrap, timeline_snapshot
from .combat_turns import initial_order
from .combat_wire import initial_timeline, topology


def _retained_carrier_packets(fight, action_id, *, area_rehydration=None):
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
        | set(getattr(fight, "native_owned_spatial_effects", {}))
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

    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    hidden = hidden_snapshot_actor_ids(fight)
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
        if uid in getattr(fight, "native_owned_spatial_effects", {}):
            sources.append(fight.native_owned_spatial_effects[uid].get("payload"))
        if uid in fight.native_owned_group_effects:
            sources.append(fight.native_owned_group_effects[uid].get("payload"))
        if len(sources) != 1 or not isinstance(sources[0], str):
            raise ValueError("Retained effect has no unique current wire payload")
        payload = bytes.fromhex(sources[0])
        manager_id = entry.manager_id
        target_id = entry.target_id if entry.target_id is not None else manager_id
        if type(manager_id) is not int or manager_id == 0 or type(target_id) is not int:
            raise ValueError("Retained effect has no current native manager")
        if target_id in hidden or manager_id in hidden:
            continue
        area = getattr(fight, "native_owned_area_effects", {}).get(uid)
        if (
            area is not None
            and area.get("executed") is True
            and area.get("native_private_area") is None
            and area["area_uid"] not in getattr(fight, "native_effect_areas", {})
        ):
            # Qs retirement leaves its creating eYQ in the authoritative Qf.
            # Replaying that creator executes eYQ.c and resurrects the removed
            # spatial object. Preserve Qf ownership, omit its retired visual.
            continue
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
        if (
            area_rehydration is not None
            and area is not None
            and area.get("executed") is True
            and area.get("native_private_area") is None
            and area["area_uid"] in getattr(fight, "native_effect_areas", {})
        ):
            # The emitted carrier must be the sole native eYQ object. A prior
            # myF registration with this UID makes Qf.p ignore its visual owner.
            area_rehydration[uid] = (manager_id, entry.effect_class)
        packets.append((opcode, body))
    return tuple(packets)


def _project_rehydrated_area_creators(effects, actor_id, area_rehydration):
    """Keep remote Qf facts except live area objects constructed by a carrier."""
    selected = {
        uid: family
        for uid, (manager, family) in area_rehydration.items()
        if manager == actor_id
    }
    if not selected:
        return effects
    from .combat_remote_effects import decode_remote_effects, encode_remote_effects
    from .combat_effect_removal import _identity_fields

    kept, seen = [], set()
    for row in decode_remote_effects(effects):
        uid = _identity_fields(row.payload, integer_fields=(1,)).get(1)
        if uid in selected:
            if row.effect_class != selected[uid] or uid in seen:
                raise ValueError("Conflicting spectator area creator Qf registration")
            seen.add(uid)
        else:
            kept.append(row)
    return encode_remote_effects(kept)


def current_snapshot(
    fight, shared, *, actor_payload, deadline_ms=None, public_pvp_duel=False
):
    """Return a native cva bootstrap and safe current retained state packets.

    `actor_payload(fight, actor)` must produce the same authoritative `(stats,
    effects)` pair used for current join bootstrap. During an active fight,
    `deadline_ms` is required and `myG` is reconstructed from the live FSM,
    never reused from placement.
    """
    if not callable(actor_payload):
        raise ValueError("Authoritative native actor serializer is required")
    if type(public_pvp_duel) is not bool:
        raise ValueError("Invalid public PvP spectator policy")
    if getattr(shared, "is_duel", False) and not public_pvp_duel:
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

    from .combat_snapshot_actor_visibility import hidden_snapshot_actor_ids

    retired_summons = hidden_snapshot_actor_ids(fight)
    actors = [
        actor for actor in fight.actors.values() if actor.id not in retired_summons
    ]
    if not actors or len(actors) > 127:
        raise ValueError("Unsupported live spectator roster size")
    from .combat_companions import bootstrap_actor_type

    participants = []
    payloads = {}
    for actor in actors:
        stats, effects = actor_payload(fight, actor)
        if not isinstance(stats, bytes) or not isinstance(effects, bytes):
            raise ValueError("Native actor serializer returned invalid payloads")
        payloads[actor.id] = (stats, effects)
        participants.append(
            dict(
                actor_id=actor.id,
                myB=bootstrap_actor_type(fight, actor),
                myn=actor.team,
                myC=1,
                myE=stats,
                myF=effects,
            )
        )

    birth_ids = set(getattr(fight, "native_summon_registrations", {})) & set(payloads)
    restore_summon_timeline = fight.phase == "active" and bool(birth_ids)
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
                if 114 not in getattr(actor, "native_fight_properties", ())
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

    if restore_summon_timeline:
        # Native cva feeds myG to SU/Tc before effect births execute. Starting
        # with the full membership would enroll a timeline summon twice when
        # its exact creation effect subsequently inserts that member.
        from .combat_delivery_boundary import initial_summon_timeline

        fight_timeline = initial_summon_timeline(fight, birth_ids)

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
        myK=environment_sections(fight) + live_area_sections(fight),
    )
    timeline_state = timeline_snapshot(3)
    area_rehydration = {}
    state_packets = (
        _retained_carrier_packets(fight, action_id, area_rehydration=area_rehydration)
        if fight.phase == "active"
        else ()
    )
    if area_rehydration:
        for participant in participants:
            identity = participant["actor_id"]
            effects = _project_rehydrated_area_creators(
                participant["myF"], identity, area_rehydration
            )
            participant["myF"] = effects
            payloads[identity] = (payloads[identity][0], effects)
    bootstrap_packet = spectator_bootstrap(
        value, phase_code=phase_code, timeline_snapshot=timeline_state
    )
    if fight.phase == "active":
        from .combat_death_script_snapshot import immediate_death_script_packets

        state_packets = tuple(state_packets) + immediate_death_script_packets(
            fight, actors, action_id
        )
    # Native buK resolves bootstrap roster IDs through bio.jv before applying
    # their stat snapshots. A summon created before this observer arrived has
    # no client entity yet; listing its ID in cva does not construct one.
    # Reinstall its exact owned creation descriptor, as owned reconnect does,
    # then overwrite constructor defaults with the current snapshot values.
    births = getattr(fight, "native_summon_creation_deliveries", {})
    creation_packets = []
    for identity in getattr(fight, "native_summon_registrations", {}):
        if identity not in payloads:
            continue
        birth = births.get(identity)
        if (
            not isinstance(birth, dict)
            or type(birth.get("opcode")) is not int
            or not isinstance(birth.get("payload_hex"), str)
        ):
            raise ValueError("Spectator snapshot lacks actual summon creation payload")
        creation_packets.append((birth["opcode"], bytes.fromhex(birth["payload_hex"])))
    current_packets = []
    if creation_packets:
        from .combat_wire import actor_state

        for identity, (stats, effects) in payloads.items():
            current_packets.extend(
                (
                    (13912, actor_state(13912, fight.id, identity, effects)),
                    (12873, actor_state(12873, fight.id, identity, stats)),
                )
            )
    import struct

    flush = (13420, struct.pack(">i", fight.id))
    packets = [bootstrap_packet]
    if creation_packets:
        packets.extend(creation_packets)
        packets.append(flush)
    packets.extend(current_packets)
    if restore_summon_timeline:
        from .combat_recovery import recovery_packet
        from .combat_phase import action_transition
        from .combat_encounter_scene_helpers import scene_helper_controller_records

        # cjk registers cvn/12053 on the spectator's same fight dispatcher;
        # cjv restores SU without a participant-owner check. Restore the full
        # counters/current member only after the native birth queue is closed.
        packets.append(
            recovery_packet(fight, struct.pack(">i", fight.id), deadline_ms=deadline_ms)
        )
        packets.append(
            action_transition(
                fight.id,
                controller_records=scene_helper_controller_records(fight),
            )
        )
    packets.extend(state_packets)
    if state_packets:
        packets.append(flush)
    return tuple(packets)
