"""Reusable native effect runtime factory for authoritative spell previews.

No default execution/targeting/stat snapshots are invented. Each provider
callback receives the same preview and plan, then the effect/invocation when
needed. Native UID allocation and the outbox stay on that preview; callers
commit and emit only after prepare_spell_transaction succeeds.
"""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import dataclass, replace
from .combat_effect_dispatch import (
    EffectDispatcher,
    EffectInvocation,
    UnsupportedEffectExecution,
)
from .combat_effect_resolver import NativeEffectResolver
from .combat_damage_handler import NativeDamageHandler
from .combat_healing_handler import NativeHealingHandler
from .combat_damage_healing import HEAL_ELEMENTS, DAMAGE_FAMILIES
from .combat_stat_handler import NativeStatHandler
from .combat_state_handler import NativeStateHandler
from .combat_level_group import runtime_group_level as native_actor_group_level
from .combat_state_level_group import runtime_child_level as native_state_group_level
from .combat_hp_level_group import runtime_group_level as native_hp_group_level
from .combat_characteristic_level_group import (
    runtime_group_level as native_characteristic_group_level,
)
from .combat_trigger_level_group import (
    runtime_group_level as native_trigger_group_level,
)
from .combat_cost_level_group import runtime_group_level as native_cost_group_level
from .combat_state_decurse import NativeStateDecurseHandler
from .combat_native_timing_context import NativeEffectTimingProvider
from .combat_native_area_metadata import merge_native_point_areas


@dataclass(frozen=True)
class NativeRuntimeContexts:
    """Explicit authoritative callbacks; every callback receives preview/plan.

    actor_candidates/resolution/native_targets/cell_eligible/condition/damage/
    healing/stat/state receive (preview, plan, effect, invocation).
    probability receives (preview, plan, probability, invocation).
    group_cells receives (preview, plan, effect, invocation).
    rounding and uid_start receive (preview, plan).
    uid_start must verify the authoritative persisted next UID or explicitly
    migrate a known snapshot. Handlers validate their returned context types.
    """

    actor_candidates: object
    resolution: object
    native_targets: object
    cell_eligible: object
    condition: object
    probability: object
    group_cells: object
    damage: object
    healing: object
    stat: object
    state: object
    rounding: object
    uid_start: object
    healing_events: object = None
    damage_block: object = None
    area_affiliation: object = None  # Actual faV.j(PV) captured eHg.bcM.
    area_obstacle_register: object = None  # Actual shared QI QK registration.
    selected_surface: object = None
    state_spell_level: object = None  # Exact eWu eq spellbook lookup for count4/5.
    state_random: object = None  # Native UK.pT bounded transaction draw.


def _merge_effects(effects, state_catalog):
    merged = dict(effects)
    identity = (
        "effect_class",
        "parameters",
        "children",
        "variant",
        "minimum_level",
        "maximum_level",
        "criteria",
        "target_masks",
        "native_target_selector",
        "native_effect_flags",
        "native_localization_enabled",
    )
    for reference, effect in state_catalog["effects"].items():
        if reference in merged:
            if any(merged[reference].get(key) != effect.get(key) for key in identity):
                raise ValueError("Conflicting native spell/state effect definition")
        else:
            merged[reference] = effect
    return merged


class NativeEffectRuntimeFactory:
    """Factory(preview, plan) -> dispatcher/private packet list.

    Families are selected by native effect class/registry metadata, never
    spell IDs. Unsupported effect families keep the dispatcher's fail-closed
    behavior. Every factory call owns fresh handlers and a fresh outbox.
    """

    def __init__(
        self,
        *,
        effects,
        state_catalog,
        characteristic_registry,
        action_id,
        contexts,
        displacement_authority=None,
        relative_group_children=None,
        random_group_children=None,
        healing_event_authority=None,
        compiled_effects=None,
        summon_authority=None,
        transaction_rng=None
    ):
        if type(action_id) is not int or not 0 < action_id < (1 << 31):
            raise ValueError("Invalid native effect action ID")
        if not isinstance(contexts, NativeRuntimeContexts) or any(
            not callable(value)
            for name, value in vars(contexts).items()
            if name
            not in (
                "healing_events",
                "damage_block",
                "area_affiliation",
                "area_obstacle_register",
                "selected_surface",
                "state_spell_level",
                "state_random",
            )
        ):
            raise ValueError("Missing authoritative native runtime context provider")
        if contexts.selected_surface is not None and not callable(
            contexts.selected_surface
        ):
            raise ValueError("Native selected surface provider must be callable")
        if contexts.state_spell_level is not None and not callable(
            contexts.state_spell_level
        ):
            raise ValueError("Native state spell-level provider must be callable")
        if contexts.state_random is not None and not callable(contexts.state_random):
            raise ValueError("Native state random provider must be callable")
        if contexts.healing_events is not None and not callable(
            contexts.healing_events
        ):
            raise ValueError("Native lifecycle event provider must be callable")
        if contexts.damage_block is not None and not callable(contexts.damage_block):
            raise ValueError("Native block RNG callback must be callable")
        if contexts.area_affiliation is not None and not callable(
            contexts.area_affiliation
        ):
            raise ValueError("Native area affiliation callback must be callable")
        if contexts.area_obstacle_register is not None and not callable(
            contexts.area_obstacle_register
        ):
            raise ValueError(
                "Native area obstacle registration callback must be callable"
            )
        if compiled_effects is None:
            self.effects = merge_native_point_areas(
                _merge_effects(effects, state_catalog)
            )
        else:
            from .combat_static_catalogs import CompiledEffects

            if (
                not isinstance(compiled_effects, CompiledEffects)
                or compiled_effects.source_effects is not effects
                or compiled_effects.source_states is not state_catalog
            ):
                raise ValueError("Compiled native catalog source identity mismatch")
            self.effects = compiled_effects.effects
        self.state_catalog = state_catalog
        self.characteristic_registry = characteristic_registry
        self.action_id = action_id
        self.contexts = contexts
        self.displacement_authority = displacement_authority
        self.relative_group_children = relative_group_children
        self.random_group_children = random_group_children
        self.summon_authority = summon_authority
        self.healing_event_authority = healing_event_authority
        from random import Random

        if transaction_rng is not None and not isinstance(transaction_rng, Random):
            raise ValueError("Unknown authoritative transaction RNG owner")
        self.transaction_rng = transaction_rng

    def __call__(self, preview, plan):
        from .combat_battleground_border import ensure_battleground_border

        ensure_battleground_border(preview)
        from .combat_environment_glyphs import ensure_environment_glyphs

        ensure_environment_glyphs(preview)
        rail_authority = getattr(self, "native_rail_movement_authority", None)
        if rail_authority is not None:
            if not callable(rail_authority):
                raise ValueError("Native rail movement authority must be callable")
            preview.native_rail_movement_authority = rail_authority
        provider = self.contexts
        next_uid = provider.uid_start(preview, plan)
        if type(next_uid) is not int or not 0 < next_uid < (1 << 63):
            raise ValueError("Missing valid authoritative running-effect UID start")
        if not hasattr(preview, "native_effect_uid_next"):
            raise ValueError(
                "Fight snapshot is missing persisted native effect UID counter"
            )
        persisted = preview.native_effect_uid_next
        if persisted is not None and (
            type(persisted) is not int
            or not 0 < persisted < (1 << 63)
            or next_uid < persisted
        ):
            raise ValueError(
                "Native effect UID start would reuse an allocated identity"
            )
        owned = (
            set(preview.owned_stat_effects)
            | set(preview.state_wire_payloads)
            | set(preview.native_owned_group_effects)
        )
        owned.update(
            entry.uid
            for actor in preview.actors.values()
            for entry in actor.state_ledger.entries
        )
        if owned and next_uid <= max(owned):
            raise ValueError("Native effect UID start conflicts with owned effects")
        preview.native_effect_uid_next = next_uid
        packets = []
        allocate = preview.allocate_effect_uid
        dispel = None
        retention = None
        if (
            plan.get("spell_id") is not None
            or plan.get("native_retained_container") is not None
        ):
            from .combat_retained_runtime import NativeRetainedRuntime

            retention = NativeRetainedRuntime(
                preview,
                packets,
                plan=plan,
                state_catalog=self.state_catalog,
                action_id=self.action_id,
                timing=NativeEffectTimingProvider(self.state_catalog),
            )
        else:
            preview.native_retained_tracking = (
                False  # Container-less legacy adapters cannot prove coverage.
            )

        def contextual(name):
            return lambda effect, invocation: getattr(provider, name)(
                preview, plan, effect, invocation
            )

        from .combat_effect_area_targets import (
            area_targets,
            area_target_context,
        )

        def candidates(effect, invocation):
            from .combat_native_actor_lookup import native_actor

            actors = tuple(
                actor
                for actor in provider.actor_candidates(
                    preview, plan, effect, invocation
                )
                if not getattr(actor, "pve_withdrawn", False)
            )
            if any(native_actor(preview, actor.id) is not actor for actor in actors):
                raise ValueError(
                    "Target candidates must belong to the same authoritative preview"
                )
            return actors + area_targets(preview)

        def target_contexts(effect, invocation):
            contexts = provider.native_targets(preview, plan, effect, invocation)
            return {
                **contexts,
                **{
                    area.id: area_target_context(area) for area in area_targets(preview)
                },
            }

        def target_position(identity):
            from .combat_native_actor_lookup import native_actor

            actor = native_actor(preview, identity)
            if actor is not None:
                return actor.position
            for area in area_targets(preview):
                if area.id == identity:
                    return area.position
            raise ValueError("Missing authoritative native target position")

        def resolution(effect, invocation):
            context = provider.resolution(preview, plan, effect, invocation)
            if retention is not None and retention.is_subscription(effect, invocation):
                if context.delivery != "immediate":
                    raise UnsupportedEffectExecution(
                        "Native subscription event replay requires an explicit activation context"
                    )
                return replace(context, delivery="registration")
            return context

        from .combat_direct_target import native_direct_target_policies
        from .combat_native_actor_lookup import native_actor

        def source_pv(effect, invocation):
            actor = native_actor(preview, invocation.caster_id)
            if actor is not None:
                return actor
            return next(
                (
                    area
                    for area in area_targets(preview)
                    if area.id == invocation.caster_id
                ),
                None,
            )

        native_resolver = NativeEffectResolver(
            actors=candidates,
            native_context=target_contexts,
            context=resolution,
            cell_eligible=contextual("cell_eligible"),
            caster=source_pv,
            direct_target_policies=native_direct_target_policies(),
        )

        def resolver(effect, invocation):
            if retention is not None and retention.is_subscription(effect, invocation):
                effect = dict(effect, _native_group_registration_verified=True)
            return native_resolver(effect, invocation)

        rng = lambda: provider.rounding(preview, plan)
        damage = NativeDamageHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("damage"),
            rng=rng,
            block_after_calculation=contextual("damage_block")
            if provider.damage_block is not None
            else None,
        )
        healing = NativeHealingHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("healing"),
            rng=rng,
        )
        stat = NativeStatHandler(
            preview,
            packets,
            self.characteristic_registry,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        from .combat_resource_loss_handler import NativeResourceLossHandler

        def loss_properties(actor):
            authority = self.summon_authority
            if authority is None or not callable(
                getattr(authority, "properties", None)
            ):
                raise ValueError("Native eVZ requires exact actor creation authority")
            return frozenset(authority.properties(preview, actor))

        loss = NativeResourceLossHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            properties=loss_properties,
            secondary_state=None,
        )
        collision_loss = None
        collision_executor = None
        if retention is not None:
            retention.stat_handler = stat
        handlers = {effect_class: damage for effect_class in DAMAGE_FAMILIES}
        handlers.update({48: loss, 55: loss})
        from .combat_spell_cost_effect import NativeSpellCostHandler

        handlers[1065] = NativeSpellCostHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        handlers[1066] = handlers[1065]
        from .combat_consume_resources import NativeConsumeResourcesHandler

        consume_resources = NativeConsumeResourcesHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        handlers[923] = consume_resources
        from .combat_maximum_resource import (
            NativeMaximumResourceHandler,
            NativeMaximumReductionHandler,
            NativePercentageHPHandler,
        )

        maximum = NativeMaximumResourceHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers.update({kind: maximum for kind in (20, 31, 41, 191)})
        from .combat_characteristic_link import (
            NativeCharacteristicLinkHandler,
            bind_characteristic_stats,
        )

        if getattr(preview, "native_characteristic_links", {}):
            bind_characteristic_stats(preview)
        handlers[1038] = NativeCharacteristicLinkHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        from .combat_death_script import NativeDeathScriptHandler

        death_script = NativeDeathScriptHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers[1099] = death_script
        from .combat_disabled_spell_level import NativeDisabledSpellLevelHandler

        disabled_spell_level = NativeDisabledSpellLevelHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers[47] = disabled_spell_level
        from .combat_kill import NativeKillHandler
        from .combat_summon_recall import NativeSummonRecallHandler
        from .combat_set_current_characteristic import (
            NativeSetCurrentCharacteristicHandler,
            FAMILIES as SET_CURRENT_FAMILIES,
        )

        kill = NativeKillHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[28] = kill
        summon_recall = NativeSummonRecallHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.summon_authority,
            actor_authority=self.summon_authority,
        )
        handlers[859] = summon_recall
        from .combat_protected_kill import NativeProtectedKillHandler

        protected_kill = NativeProtectedKillHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[332] = protected_kill
        from .combat_current_hp_restore import NativeCurrentHPRestoreHandler

        current_hp_restore = NativeCurrentHPRestoreHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[196] = current_hp_restore
        from .combat_affiliation_effect import NativeAffiliationHandler

        affiliation = NativeAffiliationHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[1030] = affiliation
        from .combat_ap_as_mp import NativeAPAsMPHandler

        ap_as_mp = NativeAPAsMPHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[808] = ap_as_mp
        set_current = NativeSetCurrentCharacteristicHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers.update({kind: set_current for kind in SET_CURRENT_FAMILIES})
        reduction = NativeMaximumReductionHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            probability=lambda chance, invocation: provider.probability(
                preview, plan, chance, invocation
            ),
        )
        handlers.update({kind: reduction for kind in (56, 57, 192)})
        from .combat_minimum_resource import NativeMinimumResourceHandler

        handlers[877] = NativeMinimumResourceHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        from .combat_cell_null import NativeCellNullHandler

        if self.summon_authority is not None:
            from .combat_summon_handler import NativeSummonHandler

            if retention is None:
                raise ValueError("Native summons require owned container authority")
            summon = NativeSummonHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                actor_authority=self.summon_authority,
                container_level=retention.container_level,
                container=retention.container,
                rng=rng,
            )
            handlers[307] = summon
            from .combat_captured_summon_handler import NativeCapturedSummonHandler

            captured_summon = NativeCapturedSummonHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                actor_authority=self.summon_authority,
                container_level=retention.container_level,
                container=retention.container,
                rng=rng,
            )
            handlers[324] = captured_summon
            from .combat_character_copy_handler import NativeCharacterCopyHandler
            from .combat_native_spell_casting import catalog as casting_catalog

            character_copy = NativeCharacterCopyHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                actor_authority=self.summon_authority,
                container_level=retention.container_level,
                container=retention.container,
                rng=rng,
                casting_definitions=casting_catalog,
            )
            handlers[1002] = character_copy
            from .combat_summon_initialization import summon_initializer

            summon.builder.initialize_states = summon_initializer(self, packets)
            captured_summon.builder.initialize_states = summon_initializer(
                self, packets
            )
            character_copy.builder.initialize_states = summon_initializer(self, packets)
            from .combat_copied_equipment_execution import equipment_initializer

            summon.initialize_equipment = equipment_initializer(self)
            character_copy.initialize_equipment = equipment_initializer(self)
        if retention is not None:
            from .combat_effect_area import NativeEffectAreaHandler

            from .combat_aura_removal import NativeAuraRemovalHandler

            aura_removal = NativeAuraRemovalHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                retention=retention,
                rng=rng,
            )
            handlers[316] = aura_removal

            area_handler = NativeEffectAreaHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                container=retention.container,
                actor_authority=self.displacement_authority,
                area_affiliation=self.contexts.area_affiliation,
                area_obstacle_register=self.contexts.area_obstacle_register,
            )
            handlers[314] = area_handler
            handlers[308] = area_handler
            from .combat_target_aura import NativeTargetAuraHandler

            target_aura = NativeTargetAuraHandler(area_handler, retention, rng=rng)
            handlers[338] = target_aura
            handlers[315] = area_handler
            handlers[339] = area_handler
            handlers[813] = area_handler
            if self.displacement_authority is not None:
                handlers[1008] = area_handler
            from .combat_area_remove import NativeAreaRemovalHandler

            area_removal = NativeAreaRemovalHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                container=retention.container,
                rng=rng,
            )
            handlers[843] = area_removal
            handlers[911] = area_removal
            from .combat_area_remove_reference import NativeAreaReferenceRemovalHandler

            area_reference_removal = NativeAreaReferenceRemovalHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                container=retention.container,
            )
            handlers[935] = area_reference_removal
        handlers[402] = NativeCellNullHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        from .combat_spell_grant import NativeSpellGrantHandler
        from .combat_area_property import NativeAreaPropertyHandler

        area_property = NativeAreaPropertyHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers[451] = area_property

        handlers[649] = NativeSpellGrantHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        from .combat_parameter_maximum import NativeParameterMaximumHandler

        parameter_maximum = NativeParameterMaximumHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        handlers.update({kind: parameter_maximum for kind in (1201, 1202)})
        handlers[986] = NativePercentageHPHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )
        handlers.update({effect_class: healing for effect_class in HEAL_ELEMENTS})
        from .combat_orientation_effect import NativeOrientationHandler

        def orientation_roll(effect, invocation):
            condition = provider.condition(preview, plan, effect, invocation)
            query = condition.random_number_query
            if not callable(query):
                raise ValueError("Missing transaction-owned native orientation RNG")
            return query(4, ()) + 1

        handlers[303] = NativeOrientationHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            authority=self.displacement_authority,
            draw_mode=orientation_roll,
        )
        from .combat_force_characteristic import NativeForcedCharacteristicHandler
        from .combat_copy_characteristic import NativeCopyCharacteristicHandler

        handlers[1001] = NativeCopyCharacteristicHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        forced = NativeForcedCharacteristicHandler(
            preview,
            packets,
            self.characteristic_registry,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        for reference, row in self.characteristic_registry["effects"].items():
            if row["runner"] not in ("eWQ", "eWR", "eXE", "eYO"):
                raise ValueError("Unsupported native characteristic registry family")
            identity = int(reference)
            if identity in handlers or identity == 304:
                raise ValueError(
                    "Native characteristic registry conflicts with effect family"
                )
            handlers[identity] = forced if row["runner"] == "eYO" else stat
        if self.displacement_authority is not None:
            from .combat_displacement import NativeDisplacementHandler, FAMILIES

            displacement = NativeDisplacementHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                authority=self.displacement_authority,
                selected_surface=self.contexts.selected_surface,
            )
            handlers.update({identity: displacement for identity in FAMILIES})
            from .combat_armor import NativeArmorHandler

            armor = NativeArmorHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                authority=self.displacement_authority,
                rng=rng,
            )
            handlers[1013] = armor

        from .combat_fight_property import NativeFightPropertyHandler

        from .combat_capture_handler import NativeCaptureHandler

        capture = NativeCaptureHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[320] = capture

        from .combat_reflect_runner import NativeReflectRunnerHandler

        reflection = NativeReflectRunnerHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[309] = reflection

        from .combat_fight_property_clear import NativeFightPropertyClearHandler

        property_clear = NativeFightPropertyClearHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
            authority=self.displacement_authority,
        )
        handlers[446] = property_clear
        handlers[447] = NativeFightPropertyHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            authority=self.displacement_authority,
        )

        from .combat_final_modifier import NativeFinalModifierHandler

        handlers[1093] = NativeFinalModifierHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
        )

        from .combat_trigger_value_handler import NativeTriggerValueHandler

        handlers[430] = NativeTriggerValueHandler(
            preview, allocate_uid=allocate, context=contextual("stat")
        )
        from .combat_redirect_runner import NativeRedirectRunnerHandler

        redirect_runner = NativeRedirectRunnerHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers[1000] = redirect_runner
        from .combat_morph_handler import NativeMorphHandler

        morph = NativeMorphHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            rng=rng,
        )
        handlers[933] = morph

        from .combat_movement_link import NativeMovementLinkHandler

        movement_link = NativeMovementLinkHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            authority=self.displacement_authority,
        )
        handlers[802] = movement_link

        from .combat_ai_control import NativeAIControlHandler, ai_control_delivery

        ai_control = NativeAIControlHandler(
            preview,
            packets,
            allocate_uid=allocate,
            context=contextual("stat"),
            authority=self.displacement_authority,
            rng=rng,
            delivery=lambda effect, invocation, **arguments: ai_control_delivery(
                preview.id, self.action_id, effect, invocation, **arguments
            ),
        )
        handlers[325] = ai_control
        from .combat_turn_suppression import NativeTurnSuppressionHandler

        turn_suppression = NativeTurnSuppressionHandler(
            preview,
            packets,
            allocate_uid=allocate,
            action_id=self.action_id,
            context=contextual("stat"),
            authority=self.displacement_authority,
            rng=rng,
        )
        handlers[667] = turn_suppression
        from .combat_additional_turn import NativeAdditionalTurnHandler

        additional_turn = NativeAdditionalTurnHandler(
            preview,
            packets,
            allocate_uid=allocate,
            action_id=self.action_id,
            context=contextual("stat"),
            authority=self.displacement_authority,
            rng=rng,
        )
        handlers[666] = additional_turn
        from .combat_turn_duration import NativeTurnDurationHandler

        turn_duration = NativeTurnDurationHandler(
            preview,
            packets,
            allocate_uid=allocate,
            action_id=self.action_id,
            context=contextual("stat"),
            authority=self.displacement_authority,
            rng=rng,
        )
        handlers[668] = turn_duration

        from .combat_carry_handler import NativeCarryHandler
        from .combat_carry_delivery import native_carry_payload, native_carry_packet

        def carry_context(effect, invocation):
            NativeCarryHandler.require_execution_context(invocation)
            return contextual("stat")(effect, invocation)

        def carry_delivery(effect, invocation, *, uid, value, qcl, timing_payload):
            NativeCarryHandler.require_execution_context(invocation)
            payload = native_carry_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                reference=invocation.reference,
                family=effect["effect_class"],
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                cell=invocation.cell,
                value=value,
                qcl=qcl,
                timing_payload=timing_payload,
                context_payload=bytes.fromhex(invocation.native_context_hex),
            )
            return native_carry_packet(
                preview.id, self.action_id, payload, family=effect["effect_class"]
            )

        def carry_selected_height(fight, x, y):
            from .combat_qi_surface_catalog import (
                native_qi_surfaces,
                native_qi_surface_provenance,
            )
            from .combat_qi_snapshot import NativeQISnapshot

            provenance = getattr(fight, "native_qi_surface_provenance", None)
            if not isinstance(provenance, dict):
                raise ValueError("Throw requires actual selected-surface provenance")
            map_id = provenance.get("map_id")
            if provenance != native_qi_surface_provenance(map_id):
                raise ValueError("Throw selected-surface provenance mismatch")
            return native_qi_surfaces(map_id).X(
                NativeQISnapshot(fight.native_qi_snapshot), x, y
            )

        carrying = NativeCarryHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=carry_context,
            authority=self.displacement_authority,
            rng=rng,
            delivery=carry_delivery,
            selected_height=carry_selected_height,
        )
        handlers[333] = carrying
        handlers[334] = carrying

        from .combat_triggered_spell_handler import NativeTriggeredSpellHandler

        def execute_triggered_spell(request, effect, invocation):
            from dataclasses import replace
            from .combat_spell_level import NativeSpellBook
            from .combat_native_spell_casting import (
                definition as ability_definition,
                catalog as ability_catalog,
            )
            from .combat_triggered_spell import (
                triggered_spell_plan,
                consume_triggered_costs,
                triggered_spell_scope,
                triggered_spell_level,
                InternalTriggeredAbility,
            )
            from .combat_active_spell import active_spell_scope
            from .combat_cast_events import cast_event_scope
            from .combat_execution_context import constructed_execution_context

            actor = preview.actors[request.caster_id]
            native = self.displacement_authority(preview, actor)
            if not isinstance(native.native_spellbook, NativeSpellBook):
                raise ValueError("Missing actual triggered-spell owned ability book")
            internal = None
            if native.native_spellbook.level(request.spell_id) == 0:
                record = ability_catalog().get(str(request.spell_id))
                maximum = None if record is None else record.get("maximum_level")
                if (
                    self.effects.get(str(invocation.reference)) is not effect
                    or effect["effect_class"] != 426
                ):
                    raise ValueError(
                        "Internal triggered ability lacks compiled dependency authority"
                    )
                internal = InternalTriggeredAbility(
                    invocation.reference, request.spell_id, maximum
                )
            level = triggered_spell_level(request, native, internal)
            partial = dict(
                actor_id=actor.id,
                spell_id=request.spell_id,
                evaluation_level=level,
                target=request.cell,
                target_id=invocation.target_id,
            )
            condition = provider.condition(
                preview, partial, effect, replace(invocation, level=level)
            )
            nested_plan = triggered_spell_plan(
                request,
                actor=actor,
                authority=native,
                condition=condition,
                definition=ability_definition,
                internal_ability=internal,
            )
            nested_plan["target_id"] = invocation.target_id
            # Explicit server policy for the empty installed eGj hook: fresh
            # nested PS constructor, independent of restored incoming PS.
            context_hex = constructed_execution_context().payload().hex()
            with triggered_spell_scope(request):
                consume_triggered_costs(actor, nested_plan, fight=preview)
                nested, nested_packets = self(preview, nested_plan)
                with active_spell_scope(
                    preview, request.spell_id, level=level
                ), preview.effect_resolution(), cast_event_scope(
                    nested, nested_plan, origin="nested"
                ):
                    for reference in nested_plan["effect_ids"]:
                        nested.execute(
                            EffectInvocation(
                                reference,
                                level,
                                actor.id,
                                invocation.target_id,
                                request.cell,
                                native_context_hex=context_hex,
                            )
                        )
                # Both outboxes stay private to the parent transaction; a
                # nested failure propagates and aborts the entire parent cast.
                packets.extend(nested_packets)

        triggered_spell = NativeTriggeredSpellHandler(
            preview,
            packets,
            action_id=self.action_id,
            allocate_uid=allocate,
            context=contextual("stat"),
            authority=self.displacement_authority,
            rng=rng,
            executor=execute_triggered_spell,
        )
        handlers[426] = triggered_spell

        from .combat_event_costs import LiveEventCostAuthority

        cost_resolver = (
            None
            if self.displacement_authority is None
            else LiveEventCostAuthority(
                preview,
                actor_authority=self.displacement_authority,
                condition_context=lambda effect, invocation, source_plan: provider.condition(
                    preview, source_plan, effect, invocation
                ),
            )
        )
        if retention is not None:
            retention.cost_resolver = cost_resolver

        def group_level(effect, values, invocation):
            if effect["effect_class"] in (910, 912):
                return native_cost_group_level(
                    effect,
                    values,
                    invocation,
                    preview.actors,
                    cost_resolver=cost_resolver,
                )
            if effect["effect_class"] == 999:
                from .combat_group_pv import resolve_group_level_pv

                return native_actor_group_level(
                    effect,
                    values,
                    invocation,
                    preview.actors,
                    active=preview.phase == "active",
                    resolve_pv=lambda identity: resolve_group_level_pv(
                        preview, identity
                    ),
                )
            if effect["effect_class"] == 844:
                return native_state_group_level(effect, values, invocation, preview)
            callback = {
                910: native_cost_group_level,
                912: native_cost_group_level,
                913: native_characteristic_group_level,
                1020: native_trigger_group_level,
                1047: native_hp_group_level,
            }[effect["effect_class"]]
            actors = preview.actors
            if effect["effect_class"] in (913, 1047):
                from .combat_group_pv import scoped_group_actors

                actors = scoped_group_actors(preview)
                from .combat_group_pv import group_pa

                return callback(
                    effect,
                    values,
                    invocation,
                    actors,
                    resolve_pa=lambda identity, stat: group_pa(preview, identity, stat),
                )
            return callback(effect, values, invocation, actors)

        from .combat_native_pt import native_pt_preflight

        def transfer_probability(fraction):
            if not isinstance(fraction, (int, float)) or not 0 <= fraction <= 1:
                raise ValueError("Native GT.l transfer fraction required")
            if fraction in (0, 1):
                return fraction == 1
            draw = rng()
            if type(draw) is not float or not 0 <= draw < 1:
                raise ValueError("Native GT.l transaction-private draw required")
            return draw < fraction

        def transfer_skip_second(effect, invocation):
            contexts = provider.native_targets(preview, plan, effect, invocation)
            if contexts.get(invocation.target_id, {}).get("is_eGj") is True:
                return False  # eGj and faO/Qq are distinct native class trees.
            raise ValueError("Missing native faO transfer exception category authority")

        from .combat_random_child_level import random_child_level
        from .combat_distance_level_group import NativeDistanceGroupRunner

        distance_group = NativeDistanceGroupRunner(
            allocate_uid=allocate,
            actor_position=target_position,
            rng=rng,
        )
        handlers[1080] = distance_group

        dispatcher = EffectDispatcher(
            self.effects,
            handlers,
            resolve=resolver,
            condition_context=lambda invocation: provider.condition(
                preview, plan, self.effects[str(invocation.reference)], invocation
            ),
            probability_accepts=lambda probability, invocation: provider.probability(
                preview, plan, probability, invocation
            ),
            group_cells=contextual("group_cells"),
            multiple_group_candidates=native_resolver.candidate_invocations,
            group_random=rng,
            actor_position=target_position,
            group_retention=retention,
            pt_preflight=native_pt_preflight,
            transfer_probability=transfer_probability,
            transfer_skip_second=transfer_skip_second,
            random_child_level=lambda parameters: random_child_level(parameters, rng),
            distance_group_runner=distance_group,
            group_level=group_level,
            random_group_children=None
            if self.random_group_children is None
            else lambda effect, values, invocation, children: self.random_group_children(
                preview, plan, effect, values, invocation, children
            ),
            relative_group_children=None
            if self.relative_group_children is None
            else lambda effect, values, invocation, children: self.relative_group_children(
                preview, plan, effect, values, invocation, children
            ),
        )
        state = NativeStateHandler(
            preview,
            packets,
            self.state_catalog,
            action_id=self.action_id,
            allocate_uid=allocate,
            rng=rng,
            state_spell_level=(
                None
                if self.contexts.state_spell_level is None
                else lambda effect, invocation, reference: self.contexts.state_spell_level(
                    preview, plan, effect, invocation, reference
                )
            ),
            state_random=(
                None
                if self.contexts.state_random is None
                else lambda limit: self.contexts.state_random(preview, plan, limit)
            ),
            context=contextual("state"),
            execute_child=dispatcher.execute,
            remove_child_effect=stat.remove,
            applied_state_scope=None
            if retention is None
            else retention.applied_state_scope,
        )
        if retention is not None:
            from .combat_retained_runtime import remove_owned_stat

            state.remove_child_effect = lambda uid: remove_owned_stat(stat, uid)
            original_remove_children = state.remove_state_children

            def remove_children(uid):
                area_uids = tuple(
                    child_uid
                    for child_uid, row in getattr(
                        preview, "native_owned_area_effects", {}
                    ).items()
                    if row.get("state_uid") == uid
                )
                if area_uids:
                    # eWu.aS removes old Qf carriers before creating the new
                    # carrier. Keep the actual old PL available to callbacks.
                    retention.removal(retention.view()).remove(area_uids)
                    retention.synchronize()
                original_remove_children(uid)
                for child_uid, row in tuple(preview.native_owned_group_effects.items()):
                    if row.get("state_uid") == uid:
                        retention.remove_group(child_uid)

            state.remove_state_children = remove_children
        dispatcher.native_state_handler = state
        dispatcher.native_retention = retention
        if retention is not None:
            from .combat_event_replay import NativeEventReplay

            dispatcher.replay_event = NativeEventReplay(dispatcher, retention)
            if provider.healing_events is not None:
                healing.event_lifecycle = provider.healing_events(
                    preview, plan, dispatcher.replay_event, retention
                )
                from .combat_ordinary_events import OrdinaryDamageEvents

                if healing.event_lifecycle is not None:
                    from .combat_cost_payment_events import NativeCostPaymentEvents

                    consume_resources.event_lifecycle_factory = (
                        lambda: NativeCostPaymentEvents.from_healing(
                            healing.event_lifecycle
                        )
                    )
                    state.event_lifecycle = healing.event_lifecycle
                    property_clear.event_lifecycle = healing.event_lifecycle
                    capture.event_lifecycle = healing.event_lifecycle
                    reflection.event_lifecycle = healing.event_lifecycle
                    death_script.event_lifecycle = healing.event_lifecycle
                    disabled_spell_level.event_lifecycle = healing.event_lifecycle
                    area_property.event_lifecycle = healing.event_lifecycle
                    distance_group.event_lifecycle = healing.event_lifecycle
                    redirect_runner.event_lifecycle = healing.event_lifecycle
                    morph.event_lifecycle = healing.event_lifecycle
                    kill.event_lifecycle = healing.event_lifecycle
                    summon_recall.event_lifecycle = healing.event_lifecycle
                    protected_kill.event_lifecycle = healing.event_lifecycle
                    current_hp_restore.event_lifecycle = healing.event_lifecycle
                    handlers[986].event_lifecycle = healing.event_lifecycle
                    affiliation.event_lifecycle = healing.event_lifecycle
                    ap_as_mp.event_lifecycle = healing.event_lifecycle
                    set_current.event_lifecycle = healing.event_lifecycle
                    if 843 in handlers:
                        handlers[843].event_lifecycle = healing.event_lifecycle
                    if self.summon_authority is not None:
                        summon.event_lifecycle = healing.event_lifecycle
                        captured_summon.event_lifecycle = healing.event_lifecycle
                        character_copy.event_lifecycle = healing.event_lifecycle
                    dispatcher.native_clone_authority = (
                        healing.event_lifecycle.authority
                    )
                    damage.event_lifecycle = OrdinaryDamageEvents.from_healing(
                        healing.event_lifecycle
                    )
                    if self.displacement_authority is not None:
                        from .combat_ordinary_events import OrdinaryDisplacementEvents

                        displacement.event_lifecycle = (
                            OrdinaryDisplacementEvents.from_healing(
                                healing.event_lifecycle
                            )
                        )
                        from .combat_ordinary_events import OrdinaryArmorEvents

                        armor.event_lifecycle = OrdinaryArmorEvents.from_healing(
                            healing.event_lifecycle
                        )
                    movement_link.event_lifecycle = healing.event_lifecycle
                    ai_control.event_lifecycle = healing.event_lifecycle
                    turn_suppression.event_lifecycle = healing.event_lifecycle
                    additional_turn.event_lifecycle = healing.event_lifecycle
                    turn_duration.event_lifecycle = healing.event_lifecycle
                    carrying.event_lifecycle = healing.event_lifecycle
                    triggered_spell.event_lifecycle = healing.event_lifecycle
                    aura_removal.event_lifecycle = healing.event_lifecycle
                    target_aura.event_lifecycle = healing.event_lifecycle
                    stat.event_lifecycle = healing.event_lifecycle
                    maximum.event_lifecycle = healing.event_lifecycle
                    from .combat_ordinary_events import OrdinaryResourceLossEvents

                    loss.event_lifecycle = OrdinaryResourceLossEvents.from_healing(
                        healing.event_lifecycle
                    )
                    if self.displacement_authority is not None:
                        from .combat_collision_source import (
                            NativeCollisionSourceAuthority,
                        )
                        from .combat_collision_resource import (
                            NativeCollisionResourceExecutor,
                        )
                        from .combat_displacement_collision import apply_collision
                        from wakfu_server.paths import DATA_ROOT
                        import json

                        collision_source = (
                            NativeCollisionSourceAuthority.from_native_catalog()
                        )
                        collision_definition = protocol_catalog.load(
                            DATA_ROOT / "collision-effect.json"
                        )

                        def collision_context(effect, invocation):
                            collision_source.definition(effect, invocation)
                            context = provider.stat(preview, plan, effect, invocation)
                            if context.retained or context.timer is not None:
                                raise ValueError(
                                    "Native eVI requires instant null-PL timing"
                                )
                            return context

                        collision_lifecycle = OrdinaryResourceLossEvents.from_healing(
                            healing.event_lifecycle
                        )
                        collision_lifecycle.synthetic_authority = collision_source

                        def collision_properties(actor):
                            authority = self.displacement_authority
                            if not callable(getattr(authority, "properties", None)):
                                raise ValueError(
                                    "Missing native collision property authority"
                                )
                            return frozenset(authority.properties(preview, actor))

                        collision_loss = NativeResourceLossHandler(
                            preview,
                            packets,
                            action_id=self.action_id,
                            allocate_uid=allocate,
                            context=collision_context,
                            rng=rng,
                            properties=collision_properties,
                            secondary_state=None,
                            event_lifecycle=collision_lifecycle,
                            delivery=lambda *args: None,
                        )

                        def collision_characteristic(actor, characteristic):
                            if getattr(actor, "native_is_area", False):
                                from .combat_state_managers import registered_area_pv
                                from .combat_effect_area import native_effect_areas
                                from .combat_fake_fighter import verified_fake_fighter

                                actual = registered_area_pv(preview, actor.id)
                                row = getattr(preview, "native_effect_areas", {}).get(
                                    actor.id
                                )
                                if row is None:
                                    row = getattr(
                                        preview, "native_retired_area_managers", {}
                                    ).get(actor.id)
                                if (
                                    actual is None
                                    or row.get("native_area_contract") != "faW"
                                ):
                                    raise ValueError(
                                        "Unaudited native area AP presence"
                                    )
                                prototype = native_effect_areas().get(
                                    str(row["reference"])
                                )
                                constructor = verified_fake_fighter(row, prototype)
                                return (
                                    characteristic in constructor["characteristic_ids"]
                                )
                            metadata = self.displacement_authority(preview, actor)
                            if metadata.targeting.get("is_eGj") is not True:
                                raise ValueError(
                                    "Missing actual native collision fighter"
                                )
                            collision_properties(actor)
                            if not isinstance(actor.effect_stats, dict):
                                raise ValueError(
                                    "Missing complete collision characteristic map"
                                )
                            return characteristic in actor.effect_stats

                        collision_executor = NativeCollisionResourceExecutor(
                            collision_loss,
                            collision_definition,
                            characteristic_present=collision_characteristic,
                        )
                        collision_loss.delivery = collision_executor.delivery
                        dispatcher.native_collision_resource_executor = (
                            collision_executor
                        )

                        def execute_collision(
                            effect,
                            invocation,
                            *,
                            uid,
                            value,
                            displaced_id,
                            collider_id,
                            loss_ap
                        ):
                            definition = retention.definition(effect, invocation)
                            return apply_collision(
                                invocation=invocation,
                                uid=uid,
                                value=value,
                                displaced_id=displaced_id,
                                collider_id=collider_id,
                                loss_ap=loss_ap,
                                ap_loss_executor=collision_executor,
                                replay=dispatcher.replay_event,
                                clone_authority=dispatcher.native_clone_authority,
                                allocate_clone_uid=allocate,
                                suppresses_level_one=definition[
                                    "event_suppresses_level_one"
                                ]
                                or 5 in effect["native_effect_flags"],
                                suppresses_all=6 in effect["native_effect_flags"],
                                suppressed=False,
                            )

                        displacement.collision_executor = execute_collision

                def prepare(effect, values, invocation):
                    if effect["effect_class"] == 421 and dispel is not None:
                        return dispel.prepare(effect, values, invocation)
                    if effect["effect_class"] == 808:
                        return ap_as_mp.prepare(effect, values, invocation)
                    if effect["effect_class"] == 316:
                        return aura_removal.prepare(effect, values, invocation)
                    if effect["effect_class"] == 338:
                        return target_aura.prepare(effect, values, invocation)
                    if effect["effect_class"] == 1030:
                        return affiliation.prepare(effect, values, invocation)
                    if (
                        effect["effect_class"] in (843, 911)
                        and effect["effect_class"] in handlers
                    ):
                        return handlers[effect["effect_class"]].prepare(
                            effect, values, invocation
                        )
                    if effect["effect_class"] == 28:
                        return kill.prepare(effect, values, invocation)
                    if effect["effect_class"] == 332:
                        return protected_kill.prepare(effect, values, invocation)
                    if effect["effect_class"] == 196:
                        return current_hp_restore.prepare(effect, values, invocation)
                    if effect["effect_class"] in SET_CURRENT_FAMILIES:
                        return set_current.prepare(effect, values, invocation)
                    if effect["effect_class"] == 320:
                        return capture.prepare(effect, values, invocation)
                    if effect["effect_class"] == 309:
                        return reflection.prepare(effect, values, invocation)
                    if effect["effect_class"] == 446:
                        return property_clear.prepare(effect, values, invocation)
                    if effect["effect_class"] == 47:
                        return disabled_spell_level.prepare(effect, values, invocation)
                    if effect["effect_class"] == 451:
                        return area_property.prepare(effect, values, invocation)
                    if effect["effect_class"] == 1080:
                        return distance_group.prepare(effect, values, invocation)
                    if effect["effect_class"] == 1000:
                        return redirect_runner.prepare(effect, values, invocation)
                    if effect["effect_class"] == 933:
                        return morph.prepare(effect, values, invocation)
                    if effect["effect_class"] == 1099:
                        return death_script.prepare(effect, values, invocation)
                    if effect["effect_class"] in (20, 31, 41, 191):
                        return maximum.prepare(effect, values, invocation)
                    if (
                        self.summon_authority is not None
                        and effect["effect_class"] == 307
                    ):
                        return summon.prepare(effect, values, invocation)
                    if (
                        self.summon_authority is not None
                        and effect["effect_class"] == 324
                    ):
                        return captured_summon.prepare(effect, values, invocation)
                    if (
                        self.summon_authority is not None
                        and effect["effect_class"] == 1002
                    ):
                        return character_copy.prepare(effect, values, invocation)
                    if effect["effect_class"] == 304:
                        return state.prepare(effect, values, invocation)
                    if effect["effect_class"] == 321:
                        return handlers[321].prepare(effect, values, invocation)
                    if (
                        self.displacement_authority is not None
                        and effect["effect_class"] == 1013
                    ):
                        return armor.prepare(effect, values, invocation)
                    if (
                        self.displacement_authority is not None
                        and effect["effect_class"] in FAMILIES
                    ):
                        return displacement.prepare(effect, values, invocation)
                    if effect["effect_class"] == 802:
                        return movement_link.prepare(effect, values, invocation)
                    if effect["effect_class"] in (48, 55):
                        return loss.prepare(effect, values, invocation)
                    current_row = stat.registry.get(str(effect["effect_class"]))
                    if current_row is not None and current_row["runner"] in (
                        "eWQ",
                        "eWR",
                    ):
                        return stat.prepare(effect, values, invocation)
                    if effect["effect_class"] in HEAL_ELEMENTS:
                        return healing.prepare(effect, values, invocation)
                    if effect["effect_class"] in DAMAGE_FAMILIES:
                        return damage.prepare(effect, values, invocation)
                    return invocation

                dispatcher.prepare_effect = prepare
            if self.healing_event_authority is not None:
                from .combat_event_replay import NativeHealingEventEmitter

                healing.emit_events = NativeHealingEventEmitter(
                    dispatcher.replay_event,
                    self.healing_event_authority,
                    preview=preview,
                    plan=plan,
                )
        elif self.healing_event_authority is not None:
            raise ValueError(
                "Healing event replay requires a complete retained-effect runtime"
            )
        if retention is not None:
            state.register_subscription = dispatcher.register_subscription
        handlers[304] = state
        timing = NativeEffectTimingProvider(self.state_catalog)

        def reapply(effect, reference, level, invocation):
            context = timing.state_reference(
                preview, plan, effect, invocation, reference, level
            )
            return state.apply_reference(
                effect, invocation, reference, level, carrier_context=context
            )

        def resource_secondary(
            resource_handler,
            effect,
            invocation,
            uid,
            caster,
            target,
            parameters,
            resource_plan,
        ):
            from dataclasses import asdict, replace

            if resource_handler.event_lifecycle is None or retention is None:
                raise ValueError(
                    "Native eVZ secondary state requires complete lifecycle authority"
                )
            # Native eVZ.d constructs eVR.j(params,fyW.guR) and eWu.a(...),
            # whose PL is null, caster/receiver the loss target, critical false.
            source = resource_handler.event_lifecycle.source(
                effect,
                invocation,
                uid=uid,
                value=resource_plan.actual,
                channel=3,
                plan=resource_plan,
            )
            secondary = replace(
                invocation,
                reference=-4,
                level=0,
                caster_id=caster,
                target_id=target,
                cell=preview.actors[target].position,
                base_uid=None,
                state_uid=None,
                native_context_hex=None,
                native_trigger_context=asdict(source),
                native_running_uid=None,
                native_value_scope=None,
                native_explicit_target=True,
                native_retained_container={"present": False},
            )
            context = timing.direct_state_reference(
                preview, secondary, parameters[0], parameters[2], critical=False
            )
            return retention.apply_state_reference(
                state, secondary, parameters[0], parameters[2], carrier_context=context
            )

        loss.secondary_state = lambda *args: resource_secondary(loss, *args)
        if collision_loss is not None:
            collision_loss.secondary_state = lambda *args: resource_secondary(
                collision_loss, *args
            )

        handlers[321] = NativeStateDecurseHandler(
            preview,
            packets,
            self.state_catalog,
            action_id=self.action_id,
            state_handler=state,
            reapply_state=reapply,
            allocate_uid=allocate,
            rng=rng,
            event_lifecycle=state.event_lifecycle,
        )
        if retention is not None:
            from .combat_dispel import NativeDispelHandler

            dispel = NativeDispelHandler(
                view_provider=retention.view,
                removal_provider=retention.removal,
                allocate_uid=allocate,
                rng=rng,
                event_lifecycle=healing.event_lifecycle,
            )
            handlers[421] = dispel
            for kind, handler in tuple(handlers.items()):
                handlers[kind] = retention.wrap(handler, state=kind in (304, 321))
        from .combat_effect_area_events import NativeAreaEventRuntime
        from .combat_effect_area import native_effect_areas

        dispatcher.native_area_events = NativeAreaEventRuntime(
            preview, dispatcher, definitions=native_effect_areas()
        )
        carrying.area_events = dispatcher.native_area_events
        import os

        if os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1":
            stat.area_events = dispatcher.native_area_events
            if retention is not None:
                area_handler.on_created = dispatcher.native_area_events.created
                area_removal.events = dispatcher.native_area_events
                area_reference_removal.events = dispatcher.native_area_events
                retention.area_events = dispatcher.native_area_events
        return dispatcher, packets
