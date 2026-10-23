"""Exploration-only characteristic contributions from owned native food states.

Combat imports the actual states through the native state handler instead.
This reducer consumes descriptor-attested, applied-level effect definitions;
it never maps an item name, state name or profession effect to a PC stat.
"""
from wakfu_server.combat_parameters import parameter_value


def bonuses(character, *, include_operations=False):
    states = character.get("consumable_states", ())
    if not isinstance(states, (list, tuple)):
        raise ValueError("Invalid owned consumable state snapshot")
    stats, percentages, unsupported = {}, {}, []
    operations = []
    resource_kinds = {}
    seen_states = set()
    for state in states:
        if (
            not isinstance(state, dict)
            or type(state.get("state_id")) is not int
            or state["state_id"] <= 0
            or state["state_id"] in seen_states
            or type(state.get("level")) is not int
            or not 0 < state["level"] <= 32767
            or type(state.get("remaining_ms")) is not int
            or state["remaining_ms"] < 0
        ):
            raise ValueError("Invalid owned consumable state characteristic source")
        seen_states.add(state["state_id"])
        if state["remaining_ms"] == 0 and state.get("clock") != "event":
            continue
        metadata = state.get("metadata", {})
        effects = metadata.get("native_effects")
        if not isinstance(effects, dict):
            raise ValueError("Missing native consumable characteristic definitions")
        definitions = {}
        for key, effect in effects.items():
            if (
                not isinstance(effect, dict)
                or type(effect.get("id")) is not int
                or effect["id"] <= 0
                or str(effect["id"]) != str(key)
                or effect["id"] in definitions
                or type(effect.get("level")) is not int
                or not 0 <= effect["level"] <= 32767
            ):
                raise ValueError("Invalid applied-level consumable effect definition")
            definitions[effect["id"]] = effect
        roots = state.get("effect_ids", metadata.get("effect_ids"))
        if not isinstance(roots, (list, tuple)):
            raise ValueError("Missing native consumable state roots")
        controls = metadata.get("counter_control_effect_ids", ())
        if not isinstance(controls, (list, tuple)) or any(
            type(identity) is not int
            or identity not in definitions
            or definitions[identity].get("generic") not in (321, 330)
            for identity in controls
        ):
            raise ValueError("Invalid native consumable counter control definitions")
        combat_only = metadata.get("combat_only_effect_ids", ())
        if not isinstance(combat_only, (list, tuple)):
            raise ValueError("Invalid native combat-only consumable roots")
        for identity in combat_only:
            if (
                type(identity) is not int
                or identity not in roots
                or identity not in definitions
            ):
                raise ValueError("Missing attested native combat-only consumable root")
            node = definitions[identity]
            masks = node.get("native_metadata", {}).get("target_masks")
            if (
                (node.get("generic"), node.get("runner"))
                not in ((330, "eYg"), (1020, "eYw"))
                or node.get("subscription") is not True
                or not isinstance(masks, list)
                or len(masks) != 7
                or any(
                    mask is not None
                    and (
                        not isinstance(mask, list)
                        or any(type(bit) is not int for bit in mask)
                    )
                    for mask in masks
                )
            ):
                raise ValueError("Unproven native combat-only consumable subscription")
            events = {bit for index in (0, 1, 3, 4, 5) for bit in (masks[index] or ())}
            # Native eYg food subscriptions can react at fight start/end as
            # well as damage/turn boundaries. Their conditional children must
            # remain in combat; exploration never fabricates their benefits.
            allowed_events = (
                {2, 1001, 1026, 1028} if node["generic"] == 330 else {2, 1001}
            )
            if not events or not events <= allowed_events:
                raise ValueError("Unsupported native combat-only consumable event")

        def visit(identity, ancestors=()):
            if (
                type(identity) is not int
                or identity in ancestors
                or identity not in definitions
            ):
                raise ValueError("Invalid native consumable characteristic effect tree")
            effect = definitions[identity]
            if identity in controls:
                return  # The durable counter lifecycle owns these native controls.
            if identity in combat_only:
                return  # Qualified combat subscriptions remain in the native state tree.
            native = effect.get("native_metadata", {})
            runner = effect.get("runner")
            if runner in ("eXE", "eZi", "eXx"):
                return  # Marker, state-removal and profession paths are separate.
            selector = native.get("native_target_selector")
            if (
                effect.get("criteria")
                or effect.get("subscription") is not False
                or not isinstance(selector, dict)
                or selector.get("class") != "fcE"
                or selector.get("mask") not in (0, 1, 2, 3)
            ):
                unsupported.append(
                    dict(
                        state_id=state["state_id"],
                        effect_id=identity,
                        reason="contextual-consumable-characteristic",
                    )
                )
                return
            if runner == "eYg":
                for child in effect.get("children", ()):
                    visit(child, (*ancestors, identity))
                return
            values, params, stat = (
                effect.get("values"),
                effect.get("params"),
                effect.get("stat_id"),
            )
            if (
                isinstance(values, list)
                and all(type(value) is int for value in values)
                and isinstance(params, list)
                and len(params) == len(values) * 2
                and [
                    parameter_value(params, index, effect["level"])
                    for index in range(len(values))
                ]
                == values
            ):
                values = [
                    parameter_value(params, index, state["level"])
                    for index in range(len(values))
                ]
            else:
                values = None
            if runner == "eZI" and effect.get("generic") == 986:
                if (
                    not isinstance(values, list)
                    or len(values) != 1
                    or len(params) != 2
                    or effect.get("children") not in ([], ())
                    or native.get("target_masks") != [None] * 7
                ):
                    unsupported.append(
                        dict(
                            state_id=state["state_id"],
                            effect_id=identity,
                            reason="unsupported-consumable-hp-percentage",
                        )
                    )
                    return
                # Original eZI writes additive PA.om; it does not add flat HP.
                percentages[1] = percentages.get(1, 0) + values[0]
                return
            if runner == "eWO":
                # The same native eWO families as NativeMaximumReductionHandler.
                # One parameter has deterministic chance100 and reduces both
                # native bounds/current; contextual copies and chances stay out.
                resource = {56: 2, 57: 3, 192: 4}.get(effect.get("generic"))
                if (
                    resource is None
                    or stat not in (None, resource)
                    or not isinstance(values, list)
                    or len(values) != 1
                    or len(params) != 2
                    or values[0] in (-1, -2)
                    or effect.get("children") not in ([], ())
                    or native.get("target_masks") != [None] * 7
                ):
                    unsupported.append(
                        dict(
                            state_id=state["state_id"],
                            effect_id=identity,
                            reason="unsupported-consumable-resource-reduction",
                        )
                    )
                    return
                stats[resource] = stats.get(resource, 0) - values[0]
                resource_kinds[len(operations)] = dict(
                    family="eWO",
                    stat=resource,
                    reduce_current=True,
                    restore_current=True,
                )
                operations.append((resource, values[0], True))
                return
            if (
                runner in ("eWQ", "eWR")
                and stat is None
                and isinstance(values, list)
                and len(values) == 3
                and type(values[2]) is int
            ):
                stat = values[2] & 255  # eWW.C's explicit dynamic PC argument.
            if (
                runner not in ("eWQ", "eWR", "eWN")
                or type(stat) is not int
                or not 0 <= stat <= 255
                or not isinstance(values, list)
                or any(type(value) is not int for value in values)
                or not isinstance(params, list)
                or len(params) != len(values) * 2
                or [
                    parameter_value(params, index, state["level"])
                    for index in range(len(values))
                ]
                != values
                or not values
                or values[0] in (-1, -2)
                or (
                    runner in ("eWQ", "eWR")
                    and (
                        len(values) not in (1, 2, 3)
                        or len(values) > 1
                        and values[1] != 0
                    )
                )
                or (runner == "eWN" and (len(values) != 3 or values[1:] != [1, 0]))
            ):
                unsupported.append(
                    dict(
                        state_id=state["state_id"],
                        effect_id=identity,
                        reason="unsupported-consumable-characteristic",
                    )
                )
                return
            if stat in (2, 3, 4):
                flags = native.get("native_effect_flags")
                if (
                    runner != "eWN"
                    or not isinstance(flags, (list, tuple))
                    or any(type(flag) is not int for flag in flags)
                ):
                    unsupported.append(
                        dict(
                            state_id=state["state_id"],
                            effect_id=identity,
                            reason="unsupported-consumable-resource-operation",
                        )
                    )
                    return
                resource_kinds[len(operations)] = dict(
                    family="eWN",
                    stat=stat,
                    apply_current=True,
                    remove_current=False,
                    cap=None if 17 in flags else {2: 16, 3: 8}.get(stat),
                )
            delta = -values[0] if runner == "eWR" else values[0]
            stats[stat] = stats.get(stat, 0) + delta
            operations.append((stat, values[0], runner == "eWR"))

        for identity in roots:
            visit(identity)
    result = dict(stats=stats, unsupported=unsupported)
    if percentages:
        result["percentages"] = percentages
    if include_operations:
        result["stat_operations"] = tuple(operations)
        result["resource_kinds"] = resource_kinds
    return result


def reconcile_health(db, character):
    """Reconfigure exploration maximum while preserving canonical wounds/death.

    The caller owns the character lock and outside-combat lifecycle boundary.
    Expiry and replacement use the same reducer as initial consumption.
    """
    from wakfu_server.equipment_stats import effective_character
    from wakfu_server.health_policy import reconfigure

    maximum = effective_character(character, include_consumable_buffs=True)["max_hp"]
    if maximum == character["max_hp"]:
        return character
    hp = reconfigure(db, character, maximum)
    db.execute(
        "UPDATE character_regeneration SET initial_hp=%s,started_at=CURRENT_TIMESTAMP,"
        "last_at=CURRENT_TIMESTAMP WHERE character_id=%s",
        (hp, character["id"]),
    )
    return dict(character, hp=hp, max_hp=maximum)
