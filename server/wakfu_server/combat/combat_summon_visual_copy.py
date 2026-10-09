"""Source-backed bje.ac/controller -> bPi copied visual construction.

Visual state is installed after real controller/roster registration. This is not
an inventory/stat clone and never gives a bje player characteristics or type.
"""
from copy import deepcopy


def plan_summon_visual_copy(authority, fight, caster):
    from .combat_character_copy_codec import connected_copy_appearance
    from .combat_character_copy_equipment import copied_equipment_source
    from .combat_runtime_adapter import NativeActorAuthority

    metadata = authority(fight, caster)
    if (
        not isinstance(metadata, NativeActorAuthority)
        or metadata.native_actor_type != 0
        or metadata.native_is_ehp is not True
    ):
        raise ValueError("Missing native bPi connected bjo visual source")
    appearance = connected_copy_appearance(authority, fight, caster)
    equipment = copied_equipment_source(metadata, caster.id)
    return dict(
        producer="bje.ac.bPi.connected_bjo.v1",
        source_actor_id=caster.id,
        model=appearance.model,
        appearance_hex=appearance.appearance.hex(),
        categories=[list(row) for row in appearance.categories],
        equipment=deepcopy(equipment),
        source="bPi.a.bwX_Dt_Di.eRl_blp.don.PJ",
    )


def install_summon_visual_copy(
    fight, actor, caster, authority, *, equipment_apply=None
):
    plan = getattr(actor, "native_pending_summon_visual_copy", None)
    replication = getattr(actor, "native_pending_summon_equipment_replication", None)
    if plan is None and replication is None:
        return False
    registration = getattr(fight, "native_summon_registrations", {}).get(actor.id)
    if (
        fight.actors.get(actor.id) is not actor
        or not isinstance(registration, dict)
        or registration.get("controller_id") != caster.id
        or actor.native_controller_id != caster.id
        or (plan is not None and plan.get("source_actor_id") != caster.id)
    ):
        raise ValueError("Missing native bje.ac registered visual controller")
    target_metadata = authority(fight, actor)
    from .combat_property_stack import property_present
    from .combat_runtime_adapter import NativeActorAuthority

    if (
        not isinstance(target_metadata, NativeActorAuthority)
        or target_metadata.is_summon is not True
        or target_metadata.native_actor_type != 1
        or (
            plan is not None
            and not property_present(actor.native_fight_property_counts, 101)
        )
    ):
        raise ValueError("Missing actual native bje visual-copy property")
    # Revalidate live operands at the actual ac(controller) boundary. The
    # earlier plan authorizes no pre-registration visual/state mutation.
    if plan is not None and plan != plan_summon_visual_copy(authority, fight, caster):
        raise ValueError("Changed native bPi copied visual source")
    if replication is not None:
        from .combat_character_copy_equipment import copied_equipment_source

        if target_metadata.breed_id != 3251 or replication != copied_equipment_source(
            authority(fight, caster), caster.id
        ):
            raise ValueError("Changed native eZl3251 equipment source")
    calls = []
    sources = ([plan["equipment"]] if plan is not None else []) + (
        [replication] if replication is not None else []
    )
    if any(
        source.get("native_plan", {}).get("roots") for source in sources
    ) and not callable(equipment_apply):
        raise ValueError("Missing native copied cosmetic equipment effect producer")
    if plan is not None:
        actor.native_summon_visual_copy = deepcopy(plan)
        actor.native_character_copy_equipment_source = deepcopy(plan["equipment"])
        calls.append(dict(callsite="bje.ac.bPi.PJ", **deepcopy(plan["equipment"])))
        if callable(equipment_apply):
            equipment_apply(fight, actor, plan["equipment"])
        del actor.native_pending_summon_visual_copy
    if replication is not None:
        actor.native_summon_equipment_replication_source = deepcopy(replication)
        calls.append(dict(callsite="eZl.c.reference3251.PJ", **deepcopy(replication)))
        if callable(equipment_apply):
            equipment_apply(fight, actor, replication)
        del actor.native_pending_summon_equipment_replication
    actor.native_summon_equipment_calls = calls
    return True
