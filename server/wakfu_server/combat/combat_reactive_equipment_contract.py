"""Finite reactive state graph qualification; gameplay is owned by native runners.

This contract grants no event or target context. It inspects passive state roots
whose complete closure uses the reviewed turn-to-damage counter shape. It is
private until paid lifecycle and isolation acceptance qualify its integration.
"""
import ast

from .combat_definitions import effect_profile, state_profile
from .combat_local_criteria import parse_local_criterion
from .combat_operation_registry import assess_operation


_FUNCTIONS = frozenset(
    ("HasState", "HasStateFromUser", "IsEnemy", "IsTriggeredByMeleeEffect")
)
_SELECTORS = frozenset((0, 1, 2, 8194, 8200))


def _ordered_counter_topology(source, compiled):
    """Match the reviewed native topology with references derived from edges.

    State IDs only establish internal graph relationships. They never identify
    an item or activate an otherwise unsupported graph by catalog presence.
    """
    effects, states = compiled.effects, compiled.source_states["states"]
    item_level = source["native_retained_container"]["level"]

    def node(reference, family):
        effect = effects[str(reference)]
        if effect["effect_class"] != family:
            raise ValueError("Unexpected reactive edge family")
        return effect

    def state_id(effect, level):
        return effect_profile(effect, level)["parameters"][0]

    def only_child(effect, family):
        children = effect.get("children", ())
        if len(children) != 1:
            raise ValueError("Unexpected reactive child count")
        return node(children[0], family)

    def state_child(reference, family):
        children = states[str(reference)]["effect_ids"]
        if len(children) != 1:
            raise ValueError("Unexpected reactive state child count")
        return node(children[0], family)

    def criterion(effect, expected):
        text = effect.get("criteria", "").strip()
        if not text or not expected:
            return text == expected
        return ast.dump(
            parse_local_criterion(text), include_attributes=False
        ) == ast.dump(parse_local_criterion(expected), include_attributes=False)

    try:
        for reference in source["roots"]:
            root = node(reference, 304)
            permanent = state_id(root, item_level)
            turn = state_child(permanent, 330)
            if not criterion(turn, ""):
                return "reactive_turn_criterion_not_reviewed"
            if tuple(turn["target_masks"][5] or ()) != (1001,):
                return "reactive_turn_edge_not_reviewed"
            damage = only_child(turn, 330)
            if tuple(damage["target_masks"][3] or ()) != (2,):
                return "reactive_damage_edge_not_reviewed"
            children = damage.get("children", ())
            if len(children) != 3:
                return "reactive_charge_order_not_reviewed"
            melee, distance, completion = (
                node(children[0], 304),
                node(children[1], 304),
                node(children[2], 330),
            )
            melee_state, distance_state = state_id(melee, 1), state_id(distance, 1)
            branches = completion.get("children", ())
            if len(branches) != 5:
                return "reactive_completion_order_not_reviewed"
            announcement, area_group, cooldown, remove_distance, remove_melee = (
                node(branches[0], 400),
                node(branches[1], 330),
                node(branches[2], 304),
                node(branches[3], 321),
                node(branches[4], 321),
            )
            if announcement.get("children") or announcement.get("parameters"):
                return "reactive_noop_parameters_not_reviewed"
            buff = only_child(area_group, 304)
            buff_state, cooldown_state = state_id(buff, 1), state_id(cooldown, 1)
            if (
                len(
                    {permanent, melee_state, distance_state, buff_state, cooldown_state}
                )
                != 5
            ):
                return "reactive_state_aliasing_not_reviewed"
            # Roles are derived from edges, never from catalog identities.
            for identity, clock_actor, at_end, duration in (
                (permanent, "target", False, -1),
                (melee_state, "caster", True, 1),
                (distance_state, "caster", True, 1),
                (buff_state, "caster", False, 1),
                (cooldown_state, "caster", True, 1),
            ):
                for state_level in (0, 1):
                    profile = state_profile(
                        compiled.source_states, identity, state_level
                    )
                    if (
                        profile["clock_actor"] != clock_actor
                        or profile["tick_at_turn_end"] is not at_end
                        or profile["duration"] != duration
                        or profile["realtime_duration"] != 0
                        or any(
                            profile[flag] is not False
                            for flag in (
                                "additive",
                                "replace",
                                "refresh",
                                "protected",
                                "skip_turn_timer",
                            )
                        )
                    ):
                        return "reactive_state_role_clock_not_reviewed"
            melee_noop, distance_noop, cooldown_noop = (
                state_child(melee_state, 400),
                state_child(distance_state, 400),
                state_child(cooldown_state, 400),
            )
            scalar_children = states[str(buff_state)]["effect_ids"]
            if len(scalar_children) != 1:
                return "reactive_buff_scalar_child_count_not_reviewed"
            scalar = effects[str(scalar_children[0])]
            default_timing = dict(
                esr=False,
                ryE=0,
                ryF=0.0,
                ryG=False,
                ryH=0,
                ryI=0.0,
                clock_on_caster=False,
                clock_on_target=True,
            )
            indefinite_timing = dict(default_timing, ryE=-1)
            damage_timing = dict(default_timing, esr=True, ryE=1)
            root_timing = dict(clock_on_caster=False, clock_on_target=True)
            roles = (
                (root, 0, "NONE", (), root_timing, 0),
                (turn, 1, "EFFECT_CARRIER", (), indefinite_timing, 2),
                (damage, 1, "TRIGGERING_EFFECT_TARGET", (), damage_timing, 2),
                (melee, 1, "NONE", (), default_timing, 2),
                (distance, 1, "NONE", (), default_timing, 2),
                (completion, 1, "NONE", (), default_timing, 2),
                (announcement, 1, "NONE", (), default_timing, 2),
                (area_group, 2, "NONE", (), default_timing, 2),
                (buff, 1, "NONE", (), default_timing, 2),
                (cooldown, 8194, "NONE", (), default_timing, 2),
                (remove_distance, 8200, "NONE", (), default_timing, 2),
                (remove_melee, 8200, "NONE", (), default_timing, 2),
                (melee_noop, 1, "NONE", (), indefinite_timing, 2),
                (distance_noop, 1, "NONE", (), indefinite_timing, 2),
                (cooldown_noop, 1, "NONE", (15,), indefinite_timing, 2),
                (scalar, 1, "NONE", (15,), indefinite_timing, 2),
            )
            for effect, mask, application, flags, timing, mode in roles:
                if (
                    effect["native_target_selector"] != {"class": "fcE", "mask": mask}
                    or effect.get("application_flag") != application
                    or tuple(effect.get("native_effect_flags", ())) != flags
                    or effect.get("native_timing_definition") != timing
                    or effect.get("native_execution_mode") != mode
                    or effect.get("variant") != 0
                    or effect.get("native_active_effect") is True
                ):
                    return "reactive_effect_role_context_not_reviewed"
            if not criterion(damage, f"IsEnemy() and not HasState({cooldown_state})"):
                return "reactive_damage_criterion_binding_not_reviewed"
            if not criterion(
                melee,
                f'IsTriggeredByMeleeEffect() and not HasState({buff_state}, "target")',
            ):
                return "reactive_melee_criterion_binding_not_reviewed"
            if not criterion(
                distance,
                f'not IsTriggeredByMeleeEffect() and not HasState({buff_state}, "target")',
            ):
                return "reactive_distance_criterion_binding_not_reviewed"
            if not criterion(
                completion,
                f'HasStateFromUser({distance_state}, "target") and HasStateFromUser({melee_state}, "target")',
            ):
                return "reactive_owner_criterion_binding_not_reviewed"
            if (
                area_group["native_target_selector"]["mask"] != 2
                or area_group["area_native"] != "point"
                or not criterion(area_group, "")
            ):
                return "reactive_self_area_center_not_reviewed"
            if buff["area_native"] != "circle-2" or not criterion(
                buff, f'not HasState({buff_state}, "target") and not IsEnemy()'
            ):
                return "reactive_ally_area_criterion_not_reviewed"
            if cooldown["native_target_selector"]["mask"] != 8194 or not criterion(
                cooldown, ""
            ):
                return "reactive_cooldown_target_not_reviewed"
            for removal, identity in (
                (remove_distance, distance_state),
                (remove_melee, melee_state),
            ):
                if (
                    removal["native_target_selector"]["mask"] != 8200
                    or tuple(effect_profile(removal, 1)["parameters"]) != (identity,)
                    or not criterion(removal, f'HasStateFromUser({identity}, "target")')
                ):
                    return "reactive_removal_owner_binding_not_reviewed"
            for identity in (melee_state, distance_state, cooldown_state):
                noop = state_child(identity, 400)
                if (
                    noop.get("children")
                    or noop.get("parameters")
                    or not criterion(noop, "")
                ):
                    return "reactive_counter_child_not_reviewed"
            if len(states[str(buff_state)]["effect_ids"]) != 1:
                return "reactive_buff_scalar_child_count_not_reviewed"
    except (KeyError, IndexError, TypeError, ValueError):
        return "reactive_ordered_graph_incomplete_or_unknown"
    return None


def reactive_damage_state_contract(source, compiled, registry):
    """Return a deferred reason, or None for the bounded reviewed shape.

    Identity comes from native source definitions and retained parent gear;
    equipment IDs and state IDs never select admission. Unknown semantics keep
    their reason rather than falling through to blanket state activation.
    """
    if source.get("attachment_field") is not None:
        return "reactive_attachment_authority_not_qualified"
    topology = _ordered_counter_topology(source, compiled)
    if topology is not None:
        return topology
    effects, states = compiled.effects, compiled.source_states["states"]
    level = source["native_retained_container"]["level"]
    pending = [(reference, (level,), True) for reference in source["roots"]]
    if not pending:
        return "reactive_empty_source"
    seen, seen_states, events, calls, families = set(), set(), set(), set(), set()
    timed = False
    while pending:
        reference, levels, root = pending.pop()
        identity = (reference, levels, root)
        if identity in seen:
            continue
        seen.add(identity)
        effect = effects.get(str(reference))
        if effect is None:
            return "reactive_missing_definition"
        kind = effect["effect_class"]
        families.add(kind)
        if root and (kind != 304 or effect.get("children")):
            return "reactive_root_must_apply_only_native_state"
        selector = effect.get("native_target_selector")
        if (
            selector is None
            or selector.get("class") != "fcE"
            or selector.get("mask") not in _SELECTORS
            or effect.get("area_native") not in ("empty", "point", "circle-2")
        ):
            return "reactive_target_shape_not_qualified"
        if effect.get("area_native") == "circle-2" and (
            kind != 304 or selector["mask"] != 1
        ):
            return "reactive_area_operation_not_qualified"
        masks = effect.get("target_masks")
        if (
            masks is None
            or len(masks) != 7
            or any(masks[index] for index in (0, 1, 2, 4, 6))
        ):
            return "reactive_event_channel_not_qualified"
        if tuple(masks[3] or ()) not in ((), (2,)) or tuple(masks[5] or ()) not in (
            (),
            (1001,),
        ):
            return "reactive_event_identity_not_qualified"
        if masks[3] and (
            kind != 330 or effect.get("application_flag") != "TRIGGERING_EFFECT_TARGET"
        ):
            return "reactive_damage_target_binding_not_qualified"
        events.update(masks[3] or ())
        events.update(masks[5] or ())
        try:
            text = effect.get("criteria", "").strip()
            criterion = parse_local_criterion(text) if text else None
        except ValueError:
            return "reactive_condition_syntax_not_qualified"
        if criterion is not None:
            for node in ast.walk(criterion):
                if isinstance(node, ast.Call):
                    if (
                        not isinstance(node.func, ast.Name)
                        or node.func.id not in _FUNCTIONS
                    ):
                        return "reactive_condition_context_not_qualified"
                    calls.add(node.func.id)
        support = assess_operation(effect, characteristic_registry=registry)
        if support.status != "conditional":
            return "reactive_parameter_shape_not_qualified"
        scalar = registry["effects"].get(str(kind))
        if kind not in (304, 321, 330, 400) and not (
            scalar is not None
            and scalar.get("runner") == "eWQ"
            and scalar.get("dynamic_stat") is False
            and type(scalar.get("fixed_stat_id")) is int
            and scalar["fixed_stat_id"] not in (1, 2, 3, 4)
        ):
            return "reactive_operation_not_qualified"
        for current_level in levels:
            if not effect["minimum_level"] <= current_level <= effect["maximum_level"]:
                continue
            values = effect_profile(effect, current_level)
            if values["probability"] != 100:
                return "reactive_probability_not_qualified"
            parameters = values["parameters"]
            if kind != 304:
                continue
            if (
                len(parameters) != 3
                or parameters[1] != 1
                or parameters[2] != -1
                or effect["parameters"][1] != 0
            ):
                return "reactive_state_parameters_not_qualified"
            state_id = parameters[0]
            if state_id in seen_states:
                continue
            definition = states.get(str(state_id))
            if definition is None or definition.get("maximum_level") != 1:
                return "reactive_state_level_domain_not_qualified"
            seen_states.add(state_id)
            for state_level in (0, 1):
                state = state_profile(compiled.source_states, state_id, state_level)
                if state["duration"] not in (-1, 1) or state["realtime_duration"] > 0:
                    return "reactive_clock_not_qualified"
                if root and state["duration"] != -1:
                    return "reactive_root_clock_not_permanent"
                timed |= state["duration"] == 1
                pending.extend(
                    (child, (state_level,), False) for child in state["effects"]
                )
        pending.extend((child, levels, False) for child in effect.get("children", ()))
    if (
        events != {2, 1001}
        or not timed
        or not _FUNCTIONS <= calls
        or not {304, 321, 330, 400} <= families
    ):
        return "reactive_graph_not_reviewed_damage_counter_shape"
    return None
