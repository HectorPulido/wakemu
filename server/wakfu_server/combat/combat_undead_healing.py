"""Original eXs.c: initialized eXt child, without a second damage formula."""
from dataclasses import replace


def apply_undead_healing(
    healing, damage, effect, invocation, amount, parent_runner, *, actor_authority
):
    from .combat_damage_handler import NativeDamageHandler, DamageExecutionContext
    from .combat_damage_healing import HEAL_ELEMENTS
    from .combat_healing_parameters import interpret_healing_flags
    from .combat_undead_native_facts import original_fkk

    if healing.retention is None or damage.event_lifecycle is None:
        raise ValueError("Missing native undead conversion lifecycle authority")
    parent_definition = healing.retention.definition(effect, invocation)
    suppression = parent_definition.get("event_suppresses_level_one")
    if type(suppression) is not bool:
        raise ValueError("Missing native undead conversion PK suppression")
    selection = interpret_healing_flags(
        effect["native_effect_flags"],
        critical_variant=False,
        source_present=True,
        target_present=True,
        target_has_hp=True,
        undead=True,
        native_fKK=original_fkk(invocation.reference),
        native_aZB=suppression,
    )
    reference = selection["undead_damage_effect_id"]
    if reference is None:
        raise ValueError("Undead conversion cannot bypass its native child")
    # eXt.a receives already evaluated eXs.aSg. bbJ executes L2/c/L3/L4,
    # never C/fOC: no second mastery, resistance, probability or block roll.
    from .combat_property_stack import property_present

    if not callable(getattr(actor_authority, "property_counts", None)):
        raise ValueError("Missing initialized undead damage PV authority")
    target = healing.fight.actors[invocation.target_id]
    # eXt.fNd/fSb rejects PB75. This fresh child has no SPECIAL fyW.
    if property_present(actor_authority.property_counts(healing.fight, target), 75):
        parent_runner.notification_suppressed = True
        return False
    uid = healing.allocate_uid()
    child_invocation = replace(
        invocation,
        reference=reference,
        level=0,
        native_running_uid=uid,
        base_uid=None,
        state_uid=None,
        native_context_hex=None,
        native_retained_container={"present": False},
    )
    child_effect = dict(
        effect_class=1,
        variant=0,
        native_effect_flags=[],
        target_masks=[None] * 7,
        native_localization_enabled=False,
        minimum_level=0,
        maximum_level=(1 << 31) - 1,
    )
    element = HEAL_ELEMENTS[effect["effect_class"]]
    event_family = 1 if element is None else 1083 if element == 6 else element
    identifiers = dict(
        native_container={"present": False},
        effect_action_id=1,
        effect_flags=(),
        native_definition_present=True,
        native_definition_variant=0,
        zone_trigger_policy=dict(
            definition_present=True, zone_flag=False, point_area=True
        ),
    )
    definition = dict(
        effect_class=-1,
        definition_type=2,
        owner_on_caster=False,
        subscription=False,
        event_target_code=None,
        event_caster_code=None,
        event_reverse_subscription=False,
        event_global_subscription=False,
        event_priority=0,
        event_suppresses_level_one=suppression,
        event_execution_count=-1,
        event_execution_count_per_level=0.0,
        parameters=[],
        variant=0,
        minimum_level=0,
        maximum_level=(1 << 31) - 1,
    )

    class UndeadDamageEvents(type(damage.event_lifecycle)):
        def definition(self, selected, selected_invocation):
            if (
                selected_invocation.reference != reference
                or type(selected_invocation.native_running_uid) is not int
                or selected_invocation.native_running_uid <= 0
                or selected.get("effect_class") not in (1, event_family)
            ):
                raise ValueError("Changed initialized undead damage source")
            return definition

        def identifiers(self, selected, selected_invocation):
            self.definition(selected, selected_invocation)
            return dict(identifiers)

        def phase(self, selected, selected_invocation, **options):
            # Qe.baZ remains neutral1; eXt.bbx n(rDs) keeps the healing element.
            source_invocation = (
                replace(
                    selected_invocation,
                    native_trigger_context={"uid": parent_runner.uid},
                )
                if selected_invocation.native_running_uid == uid
                else selected_invocation
            )
            return super().phase(
                dict(selected, effect_class=event_family), source_invocation, **options
            )

    lifecycle = UndeadDamageEvents.__new__(UndeadDamageEvents)
    lifecycle.__dict__.update(damage.event_lifecycle.__dict__)
    child = NativeDamageHandler(
        healing.fight,
        healing.packets,
        action_id=healing.action_id,
        allocate_uid=healing.allocate_uid,
        context=damage.context,
        rng=healing.rng,
    )
    child.event_lifecycle = lifecycle
    if callable(getattr(damage, "calculated_clone_gate", None)):
        child.calculated_clone_gate = damage.calculated_clone_gate
    original_context = damage.context(child_effect, child_invocation)
    if not isinstance(original_context, DamageExecutionContext):
        raise ValueError("Missing actual initialized undead damage context")
    context = replace(original_context, critical=False, blocked=False)
    from .combat_final_modifier import NativeFinalModifier

    child.final_modifiers[uid] = NativeFinalModifier(uid, 1)
    child.prepared[uid] = (
        context,
        dict(bypass_armor_and_barrier=False),
        max(0, amount) if context.executable else None,
    )
    try:
        child(child_effect, {}, child_invocation)
    finally:
        child.cancel_prepared(child_invocation)
    parent_runner.notification_suppressed = True
