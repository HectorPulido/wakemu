"""Owned attachment preparation and atomic application through existing runners.

This module does not choose the equipment/class/aptitude ordering boundary.
The production caller must establish that boundary before enabling application.
The initial executable contract is deliberately structural, never a scroll ID
allowlist: permanent SELF states containing fixed scalar non-resource gains.
"""
from copy import deepcopy

from .combat_effect_dispatch import EffectInvocation, UnsupportedEffectExecution
from .combat_definitions import effect_profile, state_profile


def compiled_with_sources(compiled, sources):
    """Extend definitions before factory construction, preserving shared catalogs."""
    from .combat_effect_runtime import _merge_effects

    additional = {}
    for source in sources:
        for reference, effect in source["effects"].items():
            if reference in additional:
                previous = additional[reference]
            elif reference in compiled.source_effects:
                previous = compiled.source_effects[reference]
            else:
                additional[reference] = effect
                continue
            # Reuse every ordinary execution-identity collision check, even
            # when all supplied definitions already exist in the base.
            _merge_effects({reference: previous}, {"effects": {reference: effect}})
    states = compiled.source_states["effects"]
    collisions = {
        reference: states[reference] for reference in additional if reference in states
    }
    _merge_effects(additional, {"effects": collisions})
    return compiled.with_effect_delta(additional)


def immediate_scalar_contract(source, compiled, registry):
    """Return the concrete unsupported boundary, or None for the proven shape.

    Route presence alone does not authorize execution. Resource bounds, dynamic
    characteristics, event subscriptions, predicates, groups, chance and clocks
    are excluded until separately qualified with the actual owned caller.
    """
    if source.get("attachment_field") not in (24, 32):
        return "ordinary_equipment_remains_snapshot_owned"
    effects = compiled.effects
    states = compiled.source_states
    level = source["native_retained_container"]["level"]

    def common(effect, effect_level):
        if effect.get("criteria", "").strip() or effect.get("children"):
            return "conditional_or_group_execution_requires_qualification"
        masks = effect.get("target_masks")
        if masks is None or len(masks) != 7 or any(masks):
            return "event_or_target_masks_require_qualification"
        selector = effect.get("native_target_selector")
        if (
            selector is None
            or selector.get("class") != "fcE"
            or selector.get("mask") not in (0, 1)
            # eHi.bY supplies explicit PV=SELF. The native state applicator
            # uses anA/empty with selector mask0; its scalar children use
            # anD/point with mask1. Neither admits an arbitrary area target.
            or (selector.get("mask"), effect.get("area_native"))
            not in ((0, "empty"), (0, "point"), (1, "point"))
        ):
            return "nonself_target_contract_requires_qualification"
        if effect_profile(effect, effect_level)["probability"] != 100:
            return "probability_requires_qualification"
        return None

    for reference in source["roots"]:
        effect = effects.get(str(reference))
        if effect is None:
            raise UnsupportedEffectExecution("Missing owned attachment root")
        reason = common(effect, level)
        if reason:
            return reason
        values = effect_profile(effect, level)["parameters"]
        if effect["effect_class"] != 304 or len(values) != 3:
            return "nonstandard_state_root_requires_qualification"
        if values[2] not in (-1, 100) or values[1] < 0:
            return "state_chance_or_level_requires_qualification"
        state_reference = values[0]
        state_definition = states["states"].get(str(state_reference))
        if state_definition is None:
            raise UnsupportedEffectExecution("Missing owned attachment state")
        maximum = state_definition["maximum_level"]
        if type(maximum) is not int or not 0 <= maximum <= 32767:
            raise UnsupportedEffectExecution(
                "Invalid owned attachment state level bound"
            )
        # Several equipped sources can add levels to the same native state.
        # Qualifying only the first root's level could admit a later predicate,
        # subscription, timed state or unsupported child when stacking occurs.
        for state_level in range(maximum + 1):
            state = state_profile(states, state_reference, state_level)
            # fyW.guH uses negative values for indefinite realtime retention;
            # state_requires_retention documents the native sentinel semantics.
            if state["duration"] != -1 or state["realtime_duration"] > 0:
                return "state_clock_requires_qualification"
            for child in state["effects"]:
                definition = effects.get(str(child))
                if definition is None:
                    raise UnsupportedEffectExecution(
                        "Missing owned attachment state child"
                    )
                reason = common(definition, state["level"])
                if reason:
                    return reason
                contract = registry["effects"].get(str(definition["effect_class"]))
                values = effect_profile(definition, state["level"])["parameters"]
                if (
                    contract is None
                    or contract["runner"] != "eWQ"
                    or contract.get("dynamic_stat") is not False
                    or type(contract.get("fixed_stat_id")) is not int
                    or contract["fixed_stat_id"] in (1, 2, 3, 4)
                    or contract["fixed_stat_id"] < 0
                    or len(values) != 1
                    or values[0] in (-1, -2)
                ):
                    return "non_scalar_characteristic_requires_qualification"
    return None


def _ordinary_turn_state_contract(source, compiled, registry):
    """Qualify permanent self state graphs using the existing native turn motor.

    This structural subset admits state toggles, ordered groups and fixed scalar
    gains; it never executes ordinary flat item bonuses a second time. Other
    event domains and effect families remain explicit deferred sources.
    """
    if source.get("attachment_field") is not None:
        return "attachment_requires_separate_native_authority"
    effects, states = compiled.effects, compiled.source_states["states"]
    pending = [
        (reference, (source["native_retained_container"]["level"],))
        for reference in source["roots"]
    ]
    seen, seen_states = set(), set()
    for reference, _ in pending:
        root = effects.get(str(reference))
        if root is None or root["effect_class"] != 304:
            return "ordinary_nonstate_root_requires_qualification"
    while pending:
        reference, levels = pending.pop()
        key = (reference, levels)
        if key in seen:
            continue
        seen.add(key)
        effect = effects.get(str(reference))
        if effect is None:
            return "missing_ordinary_state_effect_definition"
        selector = effect.get("native_target_selector")
        if (
            selector is None
            or selector.get("class") != "fcE"
            or selector.get("mask") not in (0, 1)
            or effect.get("area_native") not in ("empty", "point")
        ):
            return "ordinary_nonself_state_requires_qualification"
        masks = effect.get("target_masks")
        if (
            masks is None
            or len(masks) != 7
            or any(masks[i] for i in (0, 1, 2, 3, 4, 6))
        ):
            return "ordinary_external_event_requires_qualification"
        if any(event not in (1001, 1002, 1037) for event in (masks[5] or ())):
            return "ordinary_external_event_requires_qualification"
        # The qualified state predicates are evaluated against the live ledger
        # by the existing native criterion implementation, never a snapshot.
        from .combat_local_criteria import parse_local_criterion
        import ast

        try:
            criterion_text = effect.get("criteria", "").strip()
            criterion = (
                parse_local_criterion(criterion_text) if criterion_text else None
            )
        except ValueError:
            return "ordinary_state_criterion_requires_qualification"
        if criterion is not None and any(
            isinstance(node, ast.Call)
            and (not isinstance(node.func, ast.Name) or node.func.id != "HasState")
            for node in ast.walk(criterion)
        ):
            return "ordinary_state_criterion_requires_qualification"
        from .combat_operation_registry import assess_operation

        support = assess_operation(effect, characteristic_registry=registry)
        if support.status != "conditional":
            return "ordinary_state_parameter_contract_requires_qualification"
        kind = effect["effect_class"]
        scalar = registry["effects"].get(str(kind))
        if kind not in (31, 304, 321, 330) and not (
            scalar is not None
            and scalar.get("runner") == "eWQ"
            and scalar.get("dynamic_stat") is False
            and type(scalar.get("fixed_stat_id")) is int
            and scalar["fixed_stat_id"] not in (1, 2, 3, 4)
        ):
            return "ordinary_state_family_requires_qualification"
        for level in levels:
            if not effect["minimum_level"] <= level <= effect["maximum_level"]:
                continue
            values = effect_profile(effect, level)
            if values["probability"] != 100:
                return "ordinary_state_probability_requires_qualification"
            if kind != 304:
                continue
            parameters = values["parameters"]
            if (
                len(parameters) != 3
                or parameters[1] < 0
                or parameters[2] not in (-1, 100)
                or effect["parameters"][1] != 0
            ):
                return "ordinary_state_parameters_require_qualification"
            state_id = parameters[0]
            if state_id in seen_states:
                continue
            definition = states.get(str(state_id))
            if (
                definition is None
                or type(definition.get("maximum_level")) is not int
                or not 0 <= definition["maximum_level"] <= 32767
            ):
                return "ordinary_state_level_domain_requires_qualification"
            seen_states.add(state_id)
            for state_level in range(definition["maximum_level"] + 1):
                state = state_profile(compiled.source_states, state_id, state_level)
                if state["duration"] != -1 or state["realtime_duration"] > 0:
                    return "ordinary_timed_state_requires_qualification"
                pending.extend((child, (state_level,)) for child in state["effects"])
        pending.extend((child, levels) for child in effect.get("children", ()))
    return None


def ordinary_turn_state_contract(source, compiled, registry):
    omitted = source.get("unplanned_passive_effect_ids")
    if not isinstance(omitted, (tuple, list)) or any(
        type(reference) is not int or reference <= 0 for reference in omitted
    ):
        return "ordinary_complete_passive_root_authority_required"
    if omitted:
        return "ordinary_incomplete_native_passive_roots_requires_qualification"
    reason = _ordinary_turn_state_contract(source, compiled, registry)
    if reason is None:
        return None
    from .combat_reactive_equipment_contract import reactive_damage_state_contract

    reactive_reason = reactive_damage_state_contract(source, compiled, registry)
    if reactive_reason is None:
        return None
    from .combat_equipment_turn_scalar_contract import turn_scalar_state_contract

    turn_reason = turn_scalar_state_contract(source, compiled, registry)
    if turn_reason is None:
        return None
    from .combat_equipment_null_carrier_contract import permanent_null_carrier_contract

    null_reason = permanent_null_carrier_contract(source, compiled, registry)
    if null_reason is None:
        return None
    from .combat_equipment_direct_marker_contract import direct_marker_contract

    marker_reason = direct_marker_contract(source, compiled, registry)
    if marker_reason is None:
        return None
    from .combat_equipment_hp_threshold_contract import hp_threshold_state_contract

    hp_reason = hp_threshold_state_contract(source, compiled, registry)
    if hp_reason is None:
        return None
    from .combat_equipment_hp_level_contract import hp_level_state_contract

    hp_level_reason = hp_level_state_contract(source, compiled, registry)
    if hp_level_reason is None:
        return None
    from .combat_equipment_start_characteristic_contract import (
        start_characteristic_state_contract,
    )

    start_reason = start_characteristic_state_contract(source, compiled, registry)
    if start_reason is None:
        return None
    from .combat_equipment_reactive_trigger_contract import (
        reactive_trigger_state_contract,
    )

    trigger_reason = reactive_trigger_state_contract(source, compiled, registry)
    if trigger_reason is None:
        return None
    from .combat_equipment_end_resource_contract import end_resource_state_contract

    end_resource_reason = end_resource_state_contract(source, compiled, registry)
    if end_resource_reason is None:
        return None
    from .combat_equipment_parity_final_contract import parity_final_state_contract

    parity_final_reason = parity_final_state_contract(source, compiled, registry)
    if parity_final_reason is None:
        return None
    from .combat_equipment_opposed_damage_contract import opposed_damage_state_contract

    opposed_reason = opposed_damage_state_contract(source, compiled, registry)
    if opposed_reason is None:
        return None
    from .combat_equipment_start_heal_contract import start_heal_state_contract

    start_heal_reason = start_heal_state_contract(source, compiled, registry)
    if start_heal_reason is None:
        return None
    from .combat_equipment_start_hp_scalar_contract import (
        start_hp_scalar_state_contract,
    )

    start_hp_scalar_reason = start_hp_scalar_state_contract(source, compiled, registry)
    return (
        None
        if start_hp_scalar_reason is None
        else "; ".join(
            (
                reason,
                reactive_reason,
                turn_reason,
                null_reason,
                marker_reason,
                hp_reason,
                hp_level_reason,
                start_reason,
                trigger_reason,
                end_resource_reason,
                parity_final_reason,
                opposed_reason,
                start_heal_reason,
                start_hp_scalar_reason,
            )
        )
    )


def prepare(
    character,
    attachment_authority,
    compiled,
    registry,
    *,
    ordinary_only=False,
    include_attachments=False,
    runtime_capability=None,
    owner_level_facts=None,
):
    from .combat_equipment_initialization import plan

    sources = plan(
        character,
        attachment_authority=attachment_authority,
        ordinary_only=ordinary_only,
        include_attachments=include_attachments,
    )
    extended = compiled_with_sources(compiled, sources)
    accepted, deferred = [], []
    capability_routes, capability_context = (
        (None, None) if runtime_capability is None else runtime_capability
    )
    for source in sources:
        generic = None
        if (
            ordinary_only
            and capability_routes is not None
            and capability_context is not None
        ):
            from .combat_equipment_operation_capability import validate_graph

            generic = validate_graph(
                source,
                extended,
                registry,
                runtime_bindings=capability_routes,
                criteria_capability=capability_context,
                owner_level_facts=owner_level_facts,
            )
        if generic is not None and generic.status == "supported":
            reason = None
        elif generic is not None and generic.status == "unsupported":
            reason = "generic operation capability rejected: " + "; ".join(
                generic.reasons
            )
        else:
            # Unknown means this generic interpreter has no authority for the
            # graph shape. Existing exact contracts remain the compatibility
            # authority; a known malformed operation stays rejected above.
            reason = (
                ordinary_turn_state_contract(source, extended, registry)
                if source.get("attachment_field") is None and ordinary_only
                else immediate_scalar_contract(source, extended, registry)
            )
        if reason is None:
            if generic is not None and generic.status == "supported":
                source = dict(source, _generic_operation_admission=True)
                if "native_owned_actor_level" in generic.requires_context:
                    from .combat_equipment_dynamic_levels import OwnerLevelFacts

                    if type(owner_level_facts) is not OwnerLevelFacts:
                        raise ValueError(
                            "Dynamic equipment graph lacks its native owner facts"
                        )
                    source["_generic_owner_level_facts"] = owner_level_facts.plain()
            accepted.append(source)
        else:
            deferred.append(
                dict(
                    uid=source["uid"],
                    source_reference=source["source_reference"],
                    attachment_field=source["attachment_field"],
                    reason=reason,
                )
            )
    return dict(compiled=extended, sources=tuple(accepted), deferred=tuple(deferred))


def initialize_transaction(fight, actor_id, preparation, runtime_factory, *, owner_id):
    """Apply already-qualified sources to a private owned preview exactly once.

    The caller owns native ordering, commit and packet delivery. No fallback
    commits partial effects; deferred source reasons remain explicit on preview.
    """
    preview = deepcopy(fight)
    actor = preview.actors.get(actor_id)
    if (
        actor is None
        or actor.hp <= 0
        or preview.phase != "active"
        or not actor.controlled
        or actor.owner_id != owner_id
        or type(owner_id) is not int
        or owner_id <= 0
    ):
        raise ValueError("Equipment initialization requires an owned active fighter")
    markers = getattr(preview, "native_owned_equipment_initializations", {})
    if actor_id in markers:
        raise ValueError("Fighter equipment effects are already initialized")
    sources = preparation["sources"]
    generic_sources = tuple(
        source
        for source in sources
        if source.get("_generic_operation_admission") is True
    )
    if generic_sources:
        capability = getattr(runtime_factory, "equipment_operation_capability", None)
        if not callable(capability):
            raise ValueError("Generic equipment admission requires its runtime factory")
        routes, _provider = capability()
        from .combat_operation_registry import RuntimeOperationBinding

        def verify_factory_routes(dispatcher):
            bindings = getattr(dispatcher, "operation_contracts", None)
            handlers = getattr(dispatcher, "handlers", None)
            if not isinstance(bindings, dict) and not hasattr(bindings, "get"):
                raise ValueError(
                    "Missing live operation bindings for generic equipment"
                )
            if not isinstance(handlers, dict):
                raise ValueError("Missing live handler table for generic equipment")
            for family, route in routes.routes.items():
                if route.inline:
                    from .combat_effect_dispatch import EffectDispatcher

                    if (
                        family not in (330, 844, 912, 913, 999, 1020, 1047)
                        or type(dispatcher) is not EffectDispatcher
                        or route.handler_type is not EffectDispatcher
                        or not callable(dispatcher.execute)
                        or dispatcher.group_retention is None
                        or family in (844, 912, 913, 999, 1020, 1047)
                        and not callable(dispatcher.group_level)
                    ):
                        raise ValueError(
                            "Live inline equipment route differs from its capability"
                        )
                    continue
                binding = bindings.get(family)
                handler = handlers.get(family)
                wrapped_runner = getattr(handler, "native_wrapped_handler", None)
                runner = handler if wrapped_runner is None else wrapped_runner
                retention_owner = getattr(handler, "native_retention_owner", None)
                wrapper_provenance = (
                    wrapped_runner is None and retention_owner is None
                ) or (
                    wrapped_runner is not None
                    and retention_owner is not None
                    and getattr(dispatcher, "native_retention", None) is retention_owner
                )
                if (
                    not isinstance(binding, RuntimeOperationBinding)
                    or binding.family != family
                    or binding.handler is not handler
                    or type(runner) is not route.handler_type
                    or not wrapper_provenance
                    or binding.contract != route.contract
                    or handler is None
                ):
                    raise ValueError(
                        "Live equipment route differs from its factory capability"
                    )

    for source in sources:
        for reference, definition in source["effects"].items():
            current = runtime_factory.effects.get(reference)
            if (
                current is None
                or any(
                    current.get(key) != definition.get(key)
                    for key in ("effect_class", "criteria", "variant")
                )
                or any(
                    tuple(current.get(key, ())) != tuple(definition.get(key, ()))
                    for key in ("parameters", "children")
                )
            ):
                raise ValueError(
                    "Owned factory predates attachment catalog composition"
                )
    packets = []
    with preview.effect_resolution():
        for source in sources:
            from .combat_equipment_dynamic_levels import verify_source_level_facts

            if not verify_source_level_facts(
                source,
                preview,
                actor_id=actor_id,
                owner_id=owner_id,
            ):
                raise ValueError(
                    "Native equipment owner-level facts changed before initialization"
                )
            container = dict(source["native_retained_container"])
            runtime_plan = {"native_retained_container": container}
            dispatcher, outbox = runtime_factory(preview, runtime_plan)
            if source.get("_generic_operation_admission") is True:
                verify_factory_routes(dispatcher)
                from .combat_equipment_retained_lifecycle import verify_initialized

                if not verify_initialized(dispatcher, preview, runtime_plan):
                    raise ValueError(
                        "Live retained equipment lifecycle differs from factory capability"
                    )
                if 1 in routes.routes:
                    from .combat_equipment_damage_capability import (
                        verify_initialized as verify_damage,
                    )

                    if not verify_damage(dispatcher, preview, runtime_plan):
                        raise ValueError(
                            "Live damage equipment lifecycle differs from factory capability"
                        )
            for reference in source["roots"]:
                dispatcher.execute(
                    EffectInvocation(
                        reference,
                        container["level"],
                        actor.id,
                        actor.id,
                        actor.position,
                        native_retained_container=container,
                        native_explicit_target=True,
                    )
                )
            packets.extend(outbox)
    markers[actor_id] = dict(
        sources=[
            dict(
                uid=source["uid"],
                reference=source["reference"],
                source_reference=source["source_reference"],
                attachment_field=source["attachment_field"],
                roots=list(source["roots"]),
            )
            for source in sources
        ],
        deferred=list(preparation["deferred"]),
    )
    preview.native_owned_equipment_initializations = markers
    return preview, tuple(packets)
