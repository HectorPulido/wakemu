"""Source-bound one-team constructor for explicitly enabled order trials.

Empty opposition is a native START layout, not a victory condition. Ordinary
PvE constructors retain their two-team requirement. This module neither enables
an admission document nor supplies a score or a synthetic opponent.
"""
from dataclasses import dataclass

# Reviewed initial side assignment; native307 retains its original team0.
PLAYER_TEAM = 1
NPC_TEAM = 0


@dataclass(frozen=True)
class ConstructorPolicy:
    owner_id: int
    account_id: int
    instance_id: int
    encounter_id: int
    mode: str
    source_sha256: str
    admission_sha256: str
    map_id: int
    player_team: int
    npc_team: int


def prepare_policy(
    proof, character, encounter_id, *, capability, context, native_source=None
):
    from wakfu_server import native_order_trial_admission as admission

    value = admission.validate(capability)
    if value["enabled"] is not True:
        raise ValueError(
            "One-team construction requires an enabled selected native mode"
        )
    source = value["sources"].get(getattr(proof, "mode", None))
    if source is not None and native_source is None:
        from wakfu_server import world_static

        native_source = next(
            (
                row
                for row in world_static.objects(source["map_id"])
                if row["id"] == source["object_id"]
            ),
            None,
        )
    if (
        value["enabled"] is not True
        or type(proof) is not admission.Admission
        or proof.generation is None
        or source is None
        or proof.mode not in ("normal", "hard")
        or proof.hard_mode is not (proof.mode == "hard")
        or proof.profile_id != value["id"]
        or proof.profile_sha256 != admission.digest(value)
        or proof.source_id != source["object_id"]
        or proof.source_map_id != source["map_id"]
        or native_source is None
        or proof.source_sha256 != admission.digest(native_source)
        or proof.descriptor_sha256 != source["descriptor_sha256"]
        or type(encounter_id) is not int
        or encounter_id <= 0
        or (
            character.get("id"),
            character.get("account_id"),
            character.get("instance_id"),
            character.get("map_id"),
        )
        != (
            proof.owner_id,
            proof.account_id,
            proof.instance_id,
            value["context"]["map_id"],
        )
        or proof.instance_id <= 0
    ):
        raise ValueError(
            "One-team construction requires an enabled selected native mode"
        )
    import struct

    planned = admission.plan(
        value,
        character,
        struct.pack(
            ">qHH", proof.source_id, source["wire_action"], source["wire_parameter"]
        ),
        native_source=native_source,
    )
    from dataclasses import replace

    if replace(planned, generation=proof.generation) != proof:
        raise ValueError("Order constructor lost its original native source")
    from wakfu_server import native_order_trial_context

    selected = native_order_trial_context.policy(context["configuration"])
    if (
        selected is None
        or selected != context["policy"]
        or selected["ready_step"] not in context["completed_steps"]
    ):
        raise ValueError("Order constructor requires its authenticated ready context")
    return ConstructorPolicy(
        proof.owner_id,
        proof.account_id,
        proof.instance_id,
        encounter_id,
        proof.mode,
        proof.source_sha256,
        proof.profile_sha256,
        character["map_id"],
        PLAYER_TEAM,
        NPC_TEAM,
    )


def validate_constructor(policy, fight_id, actors):
    actors = list(actors)
    if (
        type(policy) is not ConstructorPolicy
        or any(
            type(value) is not int or value <= 0
            for value in (
                policy.owner_id,
                policy.account_id,
                policy.instance_id,
                policy.encounter_id,
                policy.map_id,
            )
        )
        or policy.encounter_id != fight_id
        or len(actors) != 1
        or actors[0].id != policy.owner_id
        or actors[0].owner_id != policy.account_id
        or actors[0].team != policy.player_team
        or (policy.player_team, policy.npc_team) != (PLAYER_TEAM, NPC_TEAM)
        or policy.instance_id <= 0
        or policy.mode not in ("normal", "hard")
        or any(
            type(pin) is not str
            or len(pin) != 64
            or any(ch not in "0123456789abcdef" for ch in pin)
            for pin in (policy.source_sha256, policy.admission_sha256)
        )
    ):
        raise ValueError("Invalid source-bound order constructor")
    return policy


def policy_for(fight):
    policy = getattr(fight, "native_order_trial_constructor", None)
    if policy is None:
        return None
    # Native summons may populate opposition after the original solo START.
    owner = (
        fight.actors.get(policy.owner_id) if type(policy) is ConstructorPolicy else None
    )
    validate_constructor(policy, fight.id, () if owner is None else (owner,))
    return policy


def empty_opposition_allowed(fight):
    return policy_for(fight) is not None


def defer_victory(fight, alive_teams):
    policy = policy_for(fight)
    return policy is not None and policy.player_team in alive_teams


def create(proof, character, arena, *, capability, context, **resources):
    """Use the ordinary actor, QI, area and native placement constructors."""
    from .combat_bootstrap import create_placement

    policy = prepare_policy(
        proof, character, resources["fight_id"], capability=capability, context=context
    )
    if (
        arena.get("map_id") != policy.map_id
        or arena.get("native_order_instance_id") != policy.instance_id
        or type(arena.get("instance_id")) is not int
        or not 0 < arena["instance_id"] < 32768
    ):
        raise ValueError(
            "Order constructor arena differs from its selected native scope"
        )
    arena = declared_arena(arena, proof, context=context)
    from .combat_environment_participant_footprints import participant_footprints

    footprints = participant_footprints(character, ())
    existing = arena.get("native_environment_participant_footprints")
    if existing is not None and existing != footprints:
        raise ValueError("Order participant footprint differs from its native owner")
    arena["native_environment_participant_footprints"] = footprints
    fight, packets = create_placement(
        character, [], arena, native_order_policy=policy, **resources
    )
    fight.native_order_lane = arena["native_order_lane"]
    return fight, packets


def initialize(
    fight, dispatcher, proof, character, *, capability, orders, profiles=None
):
    """Publish the exact native SELF programs inside their checked scope."""
    from .native_order_trial_placement import initialization_scope

    with initialization_scope(
        fight, dispatcher, proof, character, capability=capability
    ):
        return _initialize(
            fight,
            dispatcher,
            proof,
            character,
            capability=capability,
            orders=orders,
            profiles=profiles,
        )


def _initialize(
    fight, dispatcher, proof, character, *, capability, orders, profiles=None
):
    """Install original form retention and the pinned server score checkpoint.

    The encounter owner supplies requests produced by the server's native order
    generator; this boundary accepts no packet score or client recipe selection.
    Area/state event wiring remains the native runtime's responsibility.
    """
    from . import native_order_trial_form as form
    from . import native_order_trial_checkpoint as checkpoint
    from wakfu_server import native_order_trial_rules, native_order_trial_admission

    policy = policy_for(fight)
    if (
        policy is None
        or policy.owner_id != proof.owner_id
        or policy.instance_id != proof.instance_id
        or policy.mode != proof.mode
        or dispatcher.native_state_handler.fight is not fight
        or dispatcher.native_retention.fight is not fight
    ):
        raise ValueError("Order initialization lost its actual constructor")
    plan = form.prepare_form(
        proof,
        encounter_id=fight.id,
        character=character,
        value=capability,
        profiles=profiles,
    )
    form.apply_form(dispatcher, plan, instance_id=proof.instance_id, value=capability)
    from .native_order_trial_events import BAKING_POLICY

    from .native_order_trial_movement import POLICY as MOVEMENT_POLICY
    from .native_order_trial_birth import POLICY as BIRTH_POLICY

    fight.native_order_birth_policy = dict(BIRTH_POLICY)
    fight.native_order_movement_policy = dict(MOVEMENT_POLICY)
    fight.native_order_baking_policy = dict(BAKING_POLICY)
    install_mode_flag(fight, dispatcher, proof)
    install_spawn_controller(fight, dispatcher, proof)
    rules, provenance = native_order_trial_rules.load()
    if not callable(orders):
        raise ValueError("Order initialization requires its native recipe producer")
    event_start = len(fight.events)
    orders = orders(dispatcher, proof)
    from .native_order_trial_selection import selected

    witnessed = selected(fight, tuple(fight.events[event_start:]), initialization=True)
    if witnessed is None or witnessed != orders:
        raise ValueError("Initial requests differ from their actual native selection")
    state = native_order_trial_admission.start_trial(
        proof, encounter_id=fight.id, orders=orders
    )
    checkpoint.install(
        fight, proof, state, rules, provenance=provenance, capability=capability
    )
    from .native_order_trial_presentation import synchronize

    synchronize(fight, dispatcher)
    return plan, state


def register(sessions, character, proof, fight, *, runtime):
    """Publish through the normal durable participant/Registry admission.

    Called after the caller's SQL transaction commits. The standard adapter
    verifies the real combat_fights row and current selected generation.
    """
    policy = policy_for(fight)
    if (
        policy is None
        or policy.owner_id != proof.owner_id
        or policy.instance_id != proof.instance_id
        or (character["id"], character["account_id"], character.get("instance_id"))
        != (proof.owner_id, proof.account_id, proof.instance_id)
    ):
        raise ValueError("Order publication belongs to another durable owner")
    from .native_order_trial_checkpoint import validate_fight

    if getattr(fight, "native_order_trial", None) is None:
        raise ValueError("Order publication requires its initialized checkpoint")
    validate_fight(fight)
    session = sessions.session(proof.account_id, proof.generation, character)
    return sessions.register(session, fight, runtime=runtime)


def declared_arena(arena, proof, *, context):
    """Materialize real area PV constructors at pinned reviewed floor anchors."""
    from wakfu_server import native_order_trial_context

    marker = native_order_trial_context.policy(context["configuration"])
    if marker is None or marker != context["policy"]:
        raise ValueError("Order arena lost its pinned context")
    geometry = native_order_trial_context.geometry(context["configuration"])
    layout = geometry["reviewed_arcade_layout"][proof.mode]
    if arena["map_id"] != geometry["map_id"]:
        raise ValueError("Order arena belongs to another native map")
    declarations = [
        dict(
            reference=layout["spawn_area_reference"],
            cell=layout["reviewed_spawn_anchor"],
            level=0,
        ),
        dict(
            reference=layout["escape_area_reference"],
            cell=layout["reviewed_escape_anchor"],
            level=0,
        ),
        *[
            dict(reference=row["area_reference"], cell=row["contact_anchor"], level=0)
            for row in layout["oven_contacts"]
        ],
        *[
            dict(reference=row["area_reference"], cell=row["position"], level=0)
            for row in geometry["reviewed_arcade_layout"]["barrels"]
        ],
    ]
    if any(
        tuple(row["cell"]) not in set(map(tuple, arena["validated_cells"]))
        for row in declarations
    ):
        raise ValueError("Order area lies outside its actual native arena")
    lane = dict(
        schema="reviewed-native-order-lane-v1",
        mode=proof.mode,
        geometry_sha256=marker["geometry_source"]["sha256"],
        track=[list(cell) for cell in layout["track"]],
        native_spawn_area=layout["spawn_area_reference"],
        native_orientation_effect=layout["native_orientation_effect"],
        authority=geometry["reviewed_arcade_layout"]["qualification"],
    )
    return dict(
        arena,
        native_order_lane=lane,
        native_initial_glyphs=declarations,
        native_initial_glyph_policy="wakemu.reviewed-native-order-layout-v1",
        native_initial_glyph_authority=geometry["reviewed_arcade_layout"][
            "qualification"
        ],
        native_initial_glyph_source_url="https://wakfu.fandom.com/wiki/Pizz%27larvas",
    )


def create_durable(
    db,
    store,
    character,
    proof,
    *,
    capability,
    arena,
    initialize_runtime,
    resources,
    generate_orders=None,
):
    """Build in the admitted mode's existing SQL transaction, without relocking
    its account on a second connection. Publication remains postcommit.

    Both callbacks are server runtime factories: the first initializes actual
    actor snapshots/handlers, the second executes the native request generator.
    Missing factories fail before reserving a durable combat identity.
    """
    if generate_orders is None:
        from .native_order_trial_orders import initial

        generate_orders = initial
    if not callable(initialize_runtime) or not callable(generate_orders):
        raise ValueError("Order encounter runtime constructors are unavailable")
    from contextlib import contextmanager
    from wakfu_server import fight_store, native_order_trial_context

    context = native_order_trial_context.scope(db, store, character)

    class TransactionStore:
        def __getattr__(self, name):
            return getattr(store, name)

        @contextmanager
        def connection(self):
            yield db

    fight_id = fight_store.create(
        TransactionStore(),
        proof.account_id,
        proof.generation,
        proof.owner_id,
        team=PLAYER_TEAM,
    )
    from .combat_topology_identity import reserve

    arena = dict(
        arena,
        instance_id=reserve(
            db,
            fight_id=fight_id,
            map_id=character["map_id"],
            preferred=arena["instance_id"],
        ),
    )
    options = dict(resources, fight_id=fight_id)
    fight, _ = create(
        proof, character, arena, capability=capability, context=context, **options
    )
    dispatcher = initialize_runtime(fight)
    form_plan, state = initialize(
        fight,
        dispatcher,
        proof,
        character,
        capability=capability,
        orders=generate_orders,
    )
    # Rebuild START after native3049 retention: its real myF must survive cvb.
    from .combat_bootstrap import player_payload, placement_messages

    actor = fight.actors[proof.owner_id]
    packets = placement_messages(
        fight,
        declared_arena(arena, proof, context=context),
        {actor.id: player_payload(character, actor, fight.id, wp=options["player_wp"])},
        terrain_effect_id=options["terrain_effect_id"],
        terrain_instance_id=options["terrain_instance_id"],
        leaders={
            policy_for(fight).player_team: actor.id,
            policy_for(fight).npc_team: 0,
        },
        duration_ms=options.get("duration_ms", 60000),
        viewer_id=actor.id,
    )
    return dict(
        fight=fight,
        dispatcher=dispatcher,
        packets=packets,
        arena=arena,
        form_plan=form_plan,
        state=state,
        proof=proof,
    )


def install_spawn_controller(fight, dispatcher, proof):
    """Retain original3044 on the real owner under an explicit scene policy.

    The owner attachment is reviewed reconstruction; original state roots,
    effect flags, selectors and IsSpecificArea predicates are unchanged.
    In particular this does not replace an area target with a player position.
    """
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    policy = policy_for(fight)
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if (
        policy is None
        or policy.owner_id != proof.owner_id
        or handler.fight is not fight
        or retention.fight is not fight
    ):
        raise ValueError("Native spawn controller lost its selected fight")
    actor = fight.actors[proof.owner_id]
    state = state_profile(handler.catalog, 3044, 1)
    if tuple(state["effects"]) != (118957, 118951):
        raise ValueError("Native spawn controller roots changed")
    existing = [
        entry for entry in actor.state_ledger.entries if entry.reference == 3044
    ]
    receipt = getattr(fight, "native_order_spawn_controller", None)
    if existing:
        if (
            len(existing) == 1
            and isinstance(receipt, dict)
            and receipt.get("carrier_uid") == existing[0].uid
            and receipt.get("owner_id") == actor.id
        ):
            return False
        raise ValueError("Native spawn state lacks its reviewed scene attachment")
    carrier = StateCarrierContext(
        state["duration"],
        state["realtime_duration"],
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=state["realtime_duration"]),
    )
    if not retention.apply_state_reference(
        handler,
        EffectInvocation(
            2226,
            1,
            actor.id,
            actor.id,
            actor.position,
            native_retained_container={"present": False},
        ),
        3044,
        1,
        carrier_context=carrier,
    ):
        raise ValueError("Original spawn controller carrier was not retained")
    entries = [entry for entry in actor.state_ledger.entries if entry.reference == 3044]
    if len(entries) != 1:
        raise ValueError("Native spawn controller has an ambiguous carrier")
    fight.native_order_spawn_controller = dict(
        policy="reviewed-order-owner-state3044-attachment-v1",
        owner_id=actor.id,
        carrier_uid=entries[0].uid,
        evidence="Original3044 roots/flags/selectors; missing server owner attachment reconstructed",
    )
    return True


def finish_normal(fight, runtime):
    """Close only an earned normal-mode request receipt through normal lifecycle.

    The application publishes its usual terminal event after durable settlement.
    Pending next-turn work is cancelled before this candidate is adopted.
    """
    if getattr(fight, "native_order_trial", None) is None:
        return False
    from .native_order_trial_checkpoint import validate
    from .native_order_trial_orders import POLICY

    proof, _rules, state = validate(
        fight.native_order_trial, encounter_id=fight.id, replay=False
    )
    if state.hard_mode or not state.finished or state.orders:
        return False
    if fight.phase == "finished":
        return False
    from .combat_runtime_messages import RuntimeMessages

    if (
        policy_for(fight) is None
        or getattr(fight, "native_order_request_policy", None) != POLICY
        or type(runtime) is not RuntimeMessages
        or runtime.fight is not fight
    ):
        raise ValueError("Normal order completion lacks its actual native runtime")
    from .native_order_trial_checkpoint import _digest

    witnesses = [
        event
        for event in fight.events
        if event.get("kind") == "order_requests_completed"
        and event.get("actor_id") == proof.owner_id
        and f"event:{event['sequence']}:{_digest(event)}" in state.receipts
    ]
    if len(witnesses) != 1:
        raise ValueError("Normal order completion has no unique earned request receipt")
    fight.phase = "finished"
    fight.winner = policy_for(fight).player_team
    fight._event(
        "finished",
        winner=fight.winner,
        order_completion_sequence=witnesses[0]["sequence"],
    )
    runtime._close_terminal_turn()
    return True


def install_mode_flag(fight, dispatcher, proof):
    """Original3052 level1 marks hard mode; normal keeps its native level0."""
    policy = policy_for(fight)
    handler, retention = dispatcher.native_state_handler, dispatcher.native_retention
    if (
        policy is None
        or policy.mode != proof.mode
        or policy.owner_id != proof.owner_id
        or handler.fight is not fight
        or retention.fight is not fight
    ):
        raise ValueError("Order mode marker lost its selected constructor")
    actor = fight.actors[proof.owner_id]
    existing = [
        entry for entry in actor.state_ledger.entries if entry.reference == 3052
    ]
    if proof.mode == "normal":
        if existing:
            raise ValueError("Normal mode cannot inherit the native hard flag")
        return False
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    profile = state_profile(handler.catalog, 3052, 1)
    if tuple(profile["effects"]) != (119030,):
        raise ValueError("Original hard-mode state marker changed")
    receipt = getattr(fight, "native_order_hard_flag", None)
    if existing:
        if (
            len(existing) == 1
            and existing[0].level == 1
            and receipt == dict(owner_id=actor.id, carrier_uid=existing[0].uid)
        ):
            return False
        raise ValueError("Hard-mode marker lacks its selected source")
    carrier = StateCarrierContext(
        profile["duration"],
        profile["realtime_duration"],
        False,
        None,
        None,
        False,
        False,
        False,
        0,
        native_time_payload(realtime_remaining=profile["realtime_duration"]),
    )
    if not retention.apply_state_reference(
        handler,
        EffectInvocation(
            2226,
            1,
            actor.id,
            actor.id,
            actor.position,
            native_retained_container={"present": False},
        ),
        3052,
        1,
        carrier_context=carrier,
    ):
        raise ValueError("Original hard-mode marker was not retained")
    entries = [entry for entry in actor.state_ledger.entries if entry.reference == 3052]
    if len(entries) != 1 or entries[0].level != 1:
        raise ValueError("Hard-mode marker did not retain its native level")
    fight.native_order_hard_flag = dict(owner_id=actor.id, carrier_uid=entries[0].uid)
    return True


def initial_roles(policy):
    """Typed constructor roles, without inventing an initial NPC record."""
    if (
        type(policy) is not ConstructorPolicy
        or (policy.player_team, policy.npc_team) != (PLAYER_TEAM, NPC_TEAM)
        or type(policy.map_id) is not int
        or policy.map_id <= 0
    ):
        raise ValueError("Missing reviewed native order side assignment")
    from .combat_encounter_roles import EncounterRoles

    return EncounterRoles(
        "wakemu.reviewed-native-order-one-team-v1",
        "source-qualified-native-order-constructor",
        policy.map_id,
        (),
        policy.player_team,
        policy.npc_team,
    )
