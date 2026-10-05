"""Reusable native effect runtime factory for authoritative spell previews.

No default execution/targeting/stat snapshots are invented. Each provider
callback receives the same preview and plan, then the effect/invocation when
needed. Native UID allocation and the outbox stay on that preview; callers
commit and emit only after prepare_spell_transaction succeeds.
"""
from dataclasses import dataclass, replace
from .combat_effect_dispatch import EffectDispatcher, UnsupportedEffectExecution
from .combat_effect_resolver import NativeEffectResolver
from .combat_damage_handler import NativeDamageHandler
from .combat_healing_handler import NativeHealingHandler
from .combat_damage_healing import HEAL_ELEMENTS, DAMAGE_FAMILIES
from .combat_stat_handler import NativeStatHandler
from .combat_state_handler import NativeStateHandler
from .combat_level_group import runtime_group_level as native_actor_group_level
from .combat_state_level_group import child_level as native_state_group_level
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
        summon_authority=None
    ):
        if type(action_id) is not int or not 0 < action_id < (1 << 31):
            raise ValueError("Invalid native effect action ID")
        if not isinstance(contexts, NativeRuntimeContexts) or any(
            not callable(value)
            for name, value in vars(contexts).items()
            if name not in ("healing_events", "damage_block")
        ):
            raise ValueError("Missing authoritative native runtime context provider")
        if contexts.healing_events is not None and not callable(
            contexts.healing_events
        ):
            raise ValueError("Native lifecycle event provider must be callable")
        if contexts.damage_block is not None and not callable(contexts.damage_block):
            raise ValueError("Native block RNG callback must be callable")
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

    def __call__(self, preview, plan):
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
            target_available,
        )

        def candidates(effect, invocation):
            actors = tuple(provider.actor_candidates(preview, plan, effect, invocation))
            if any(preview.actors.get(actor.id) is not actor for actor in actors):
                raise ValueError(
                    "Target candidates must belong to the same authoritative preview"
                )
            actors = tuple(
                actor
                for actor in actors
                if target_available(actor) or actor.id == invocation.caster_id
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
            if identity in preview.actors:
                return preview.actors[identity].position
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

        native_resolver = NativeEffectResolver(
            actors=candidates,
            native_context=target_contexts,
            context=resolution,
            cell_eligible=contextual("cell_eligible"),
            caster=lambda effect, invocation: preview.actors.get(invocation.caster_id),
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
        )
        handlers.update({kind: maximum for kind in (20, 31, 41, 191)})
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
            handlers[307] = NativeSummonHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                actor_authority=self.summon_authority,
                container_level=retention.container_level,
                container=retention.container,
            )
        if retention is not None:
            from .combat_effect_area import NativeEffectAreaHandler

            area_handler = NativeEffectAreaHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                container=retention.container,
            )
            handlers[315] = area_handler
            from .combat_area_remove import NativeAreaRemovalHandler

            area_removal = NativeAreaRemovalHandler(
                preview,
                packets,
                action_id=self.action_id,
                allocate_uid=allocate,
                context=contextual("stat"),
                container=retention.container,
            )
            handlers[843] = area_removal
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
                return native_actor_group_level(
                    effect,
                    values,
                    invocation,
                    preview.actors,
                    active=preview.phase == "active",
                )
            callback = {
                844: native_state_group_level,
                910: native_cost_group_level,
                912: native_cost_group_level,
                913: native_characteristic_group_level,
                1020: native_trigger_group_level,
                1047: native_hp_group_level,
            }[effect["effect_class"]]
            return callback(effect, values, invocation, preview.actors)

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
                    state.event_lifecycle = healing.event_lifecycle
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
                    stat.event_lifecycle = healing.event_lifecycle
                    from .combat_ordinary_events import OrdinaryResourceLossEvents

                    loss.event_lifecycle = OrdinaryResourceLossEvents.from_healing(
                        healing.event_lifecycle
                    )

                def prepare(effect, values, invocation):
                    if effect["effect_class"] == 304:
                        return state.prepare(effect, values, invocation)
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

        def loss_secondary(
            effect, invocation, uid, caster, target, parameters, resource_plan
        ):
            from dataclasses import asdict, replace

            if loss.event_lifecycle is None or retention is None:
                raise ValueError(
                    "Native eVZ secondary state requires complete lifecycle authority"
                )
            # Native eVZ.d constructs eVR.j(params,fyW.guR) and eWu.a(...),
            # whose PL is null, caster/receiver the loss target, critical false.
            source = loss.event_lifecycle.source(
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

        loss.secondary_state = loss_secondary

        handlers[321] = NativeStateDecurseHandler(
            preview,
            packets,
            self.state_catalog,
            action_id=self.action_id,
            state_handler=state,
            reapply_state=reapply,
        )
        if retention is not None:
            from .combat_dispel import NativeDispelHandler

            handlers[421] = NativeDispelHandler(
                view_provider=retention.view, removal_provider=retention.removal
            )
            for kind, handler in tuple(handlers.items()):
                handlers[kind] = retention.wrap(handler, state=kind in (304, 321))
        from .combat_effect_area_events import NativeAreaEventRuntime
        from .combat_effect_area import native_effect_areas

        dispatcher.native_area_events = NativeAreaEventRuntime(
            preview, dispatcher, definitions=native_effect_areas()
        )
        import os

        if os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "0") == "1":
            area_handler.on_created = dispatcher.native_area_events.created
            area_removal.events = dispatcher.native_area_events
            area_reference_removal.events = dispatcher.native_area_events
            stat.area_events = dispatcher.native_area_events
            retention.area_events = dispatcher.native_area_events
        return dispatcher, packets
