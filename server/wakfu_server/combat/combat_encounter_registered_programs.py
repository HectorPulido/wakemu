"""Reconstructed server publishers after real native summon registration.

The original server publisher is unrecovered. These explicit scene policies run
original descriptor programs in the registered fight PN, independently of the
unchanged client constructor's detached SELF-only PN. No replacement effect or
phase state is synthesized.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class RegisteredInitialProgramPolicy:
    map_id: int
    parent_reference: int
    producers: tuple
    state: int
    level: int
    initial_flag: int
    roots: tuple
    authority: str


POLICIES = {
    "wakemu.fulmoon.native_ready_point_fit.v2": RegisteredInitialProgramPolicy(
        map_id=1056,
        parent_reference=3870,
        producers=((177763, 3993), (177779, 3995), (177781, 3996), (177783, 3997)),
        state=4233,
        level=1,
        initial_flag=1,
        roots=(178024,),
        authority="wakemu.reconstructed.server-post-registration-initial-program.v1",
    ),
}
# Scene v3 adds the original field prototype; the registered program is unchanged.
POLICIES["wakemu.fulmoon.native_ready_point_fit.v3"] = POLICIES[
    "wakemu.fulmoon.native_ready_point_fit.v2"
]


def registered_program_initializer(runtime_factory, packets):
    """Create a callback sharing the original transaction and private outbox."""
    if not callable(runtime_factory) or not isinstance(packets, list):
        raise ValueError("Registered programs require actual runtime/outbox")

    def initialize(fight, actor, registration, effect, invocation):
        scene = getattr(fight, "native_encounter_scene_layout", None)
        policy = POLICIES.get(scene.get("policy")) if isinstance(scene, dict) else None
        if policy is None:
            return False
        child_reference = dict(policy.producers).get(invocation.reference)
        if child_reference is None:
            return False
        from .combat_summon_initialization import detached_actor
        from .combat_summon_initial_states import native_initial_states
        from .combat_summon import SummonRegistration
        from .combat_definitions import state_profile
        from .combat_effect_dispatch import EffectInvocation
        from .combat_state_handler import StateCarrierContext
        from .combat_native_timing_context import native_time_payload

        if (
            scene.get("map_id") != policy.map_id
            or scene.get("authority")
            != "authorized_wakemu_native_content_reconstruction"
            or scene.get("original_world_coordinates") is not False
            or fight.phase != "active"
            or fight.actors.get(actor.id) is not actor
            or detached_actor(fight, actor.id) is not None
            or not isinstance(registration, SummonRegistration)
            or registration.caster_id != invocation.caster_id
            or registration.actor_id != actor.id
            or registration.authority.breed_id != child_reference
            or effect.get("effect_class") != 307
            or runtime_factory.effects.get(str(invocation.reference)) is not effect
        ):
            raise ValueError("Registered encounter program scope changed")
        records = fight.native_summon_registrations
        row = records.get(actor.id)
        if row is None or row.get("caster_id") != registration.caster_id:
            raise ValueError("Registered program lacks actual native307 provenance")
        parent = fight.actors.get(registration.caster_id)
        parent_authority = (
            runtime_factory.summon_authority(fight, parent)
            if parent is not None
            else None
        )
        if (
            parent_authority is None
            or parent_authority.breed_id != policy.parent_reference
        ):
            raise ValueError("Registered program belongs to another original parent")
        descriptor = native_initial_states().get(str(child_reference))
        if not isinstance(descriptor, dict) or descriptor.get(
            "initial_state_triples"
        ) != [policy.state, policy.level, policy.initial_flag]:
            raise ValueError("Registered program descriptor source changed")
        receipt = dict(
            policy=scene["policy"],
            authority=policy.authority,
            original_server_publisher="unrecovered",
            producer=invocation.reference,
            parent=registration.caster_id,
            parent_reference=policy.parent_reference,
            child_reference=child_reference,
            state=policy.state,
            level=policy.level,
            roots=list(policy.roots),
        )
        prior = row.get("server_post_registration_programs", [])
        if prior:
            if prior != [receipt]:
                raise ValueError("Registered initial program receipt changed")
            return False
        if any(entry.reference == policy.state for entry in actor.state_ledger.entries):
            raise ValueError(
                "Original constructor carrier is unexpectedly still active"
            )
        dispatcher, outbox = runtime_factory(
            fight, {"native_retained_container": {"present": False}}
        )
        handler, retention = (
            dispatcher.native_state_handler,
            dispatcher.native_retention,
        )
        if handler.fight is not fight or retention.fight is not fight:
            raise ValueError("Registered program runtime changed transaction ownership")
        profile = state_profile(handler.catalog, policy.state, policy.level)
        if (
            profile["duration"] != 0
            or profile["realtime_duration"] != 0
            or tuple(profile["effects"]) != policy.roots
        ):
            raise ValueError("Registered program carrier or original roots changed")
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
        applied = retention.apply_state_reference(
            handler,
            EffectInvocation(2226, policy.level, actor.id, actor.id, actor.position),
            policy.state,
            policy.level,
            carrier_context=carrier,
            protected=True if policy.initial_flag == 0 else None,
        )
        if not applied:
            raise ValueError("Original registered initial program was not applied")
        fight.native_summon_registrations = {
            **fight.native_summon_registrations,
            actor.id: {
                **fight.native_summon_registrations[actor.id],
                "server_post_registration_programs": [receipt],
            },
        }
        packets.extend(outbox)
        return True

    return initialize
