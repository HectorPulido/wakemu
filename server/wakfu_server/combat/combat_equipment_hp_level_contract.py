"""Finite native missing-HP1047 / ordered decurse / scalar-state admission.

This checks definitions only. Native eYs arithmetic, actual HP/virtual HP PA,
state-zero semantics, mutations and retained identity remain engine-owned.
"""
from collections.abc import Mapping
from .combat_definitions import effect_profile, state_profile
from .combat_operation_registry import assess_operation

_HMI = frozenset(("rzc", "rzd", "rze", "rzf", "rzg", "rzh"))
_GROUP_RAW = (0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0.01, 3, 0)
_TIMING = frozenset(
    ("esr", "ryE", "ryF", "ryG", "ryH", "ryI", "clock_on_caster", "clock_on_target")
)


def _metadata(
    effect,
    registry,
    *,
    family,
    count,
    duration,
    end=False,
    root=False,
    masks=(None,) * 7,
    carrier=False,
    bounds=(0, 32767)
):
    selector = effect["native_target_selector"]
    timing = effect["native_timing_definition"]
    actual_masks = effect["target_masks"]
    flags = effect["native_effect_flags"]
    if (
        any(
            type(effect[key]) is not int
            for key in (
                "effect_class",
                "parameter_count",
                "variant",
                "minimum_level",
                "maximum_level",
                "native_execution_mode",
            )
        )
        or effect["effect_class"] != family
        or effect["parameter_count"] != count
        or effect["variant"] != 0
        or effect["native_execution_mode"] != (0 if root else 2)
        or (effect["minimum_level"], effect["maximum_level"]) != bounds
        or not isinstance(effect["parameters"], (tuple, list))
        or len(effect["parameters"]) != count * 2
        or any(type(value) not in (int, float) for value in effect["parameters"])
        or type(effect["criteria"]) is not str
        or effect["criteria"].strip()
        or not isinstance(selector, Mapping)
        or type(selector.get("mask")) is not int
        or selector != {"class": "fcE", "mask": 0 if root else 1}
        or effect["native_definition_class"] != ("eVE" if root else "eVy")
        or effect["area_class"] != ("anA" if root else "anD")
        or effect["area_native"] != ("empty" if root else "point")
        or effect["native_localization_enabled"] is not False
        or (root and effect.get("native_active_effect") is not False)
        or not isinstance(actual_masks, (tuple, list))
        or len(actual_masks) != 7
        or any(
            row is not None
            and (
                not isinstance(row, (tuple, list))
                or any(type(value) is not int for value in row)
            )
            for row in actual_masks
        )
        or tuple(tuple(row) if row else None for row in actual_masks) != masks
        or not isinstance(flags, (tuple, list))
        or any(type(flag) is not int for flag in flags)
        or tuple(flags) != ((1,) if carrier else (() if root else (17,)))
        or effect["application_flag"] != ("EFFECT_CARRIER" if carrier else "NONE")
        or effect["removal_flag"] != ("EFFECT_CARRIER" if carrier else "NONE")
        or type(effect["probability_base"]) not in (int, float)
        or type(effect["probability_per_level"]) not in (int, float)
        or effect["probability_base"] != 100
        or effect["probability_per_level"] != 0
    ):
        return False
    hmi = effect["native_hmi_actions"]
    if (
        not isinstance(hmi, Mapping)
        or set(hmi) != _HMI
        or any(not isinstance(rows, (tuple, list)) or rows for rows in hmi.values())
    ):
        return False
    if root:
        clock_ok = timing == {"clock_on_caster": False, "clock_on_target": True}
    else:
        clock_ok = (
            isinstance(timing, Mapping)
            and set(timing) == _TIMING
            and timing["esr"] is end
            and type(timing["ryE"]) is int
            and timing["ryE"] == duration
            and timing["ryG"] is False
            and all(
                type(timing[key]) in (int, float) and timing[key] == 0
                for key in ("ryF", "ryH", "ryI")
            )
            and timing["clock_on_caster"] is False
            and timing["clock_on_target"] is True
        )
    return (
        clock_ok
        and assess_operation(effect, characteristic_registry=registry).status
        == "conditional"
    )


def _state(catalog, reference, *, additive, effects):
    definition = catalog["states"][str(reference)]
    if (
        type(definition["maximum_level"]) is not int
        or definition["maximum_level"] != 100
        or tuple(definition["effect_ids"]) != tuple(effects)
        or definition["duration_per_level"] != 0
        or definition["realtime_duration_per_level"] != 0
    ):
        return False
    profile = state_profile(catalog, reference, 0)
    return (
        profile["duration"] == -1
        and profile["realtime_duration"] == 0
        and profile["additive"] is additive
        and profile["replace"] is False
        and profile["refresh"] is False
        and profile["protected"] is False
        and profile["clock_actor"] == "target"
        and profile["tick_at_turn_end"] is False
        and profile["skip_turn_timer"] is False
    )


def hp_level_state_contract(source, compiled, registry):
    """Return None only for the two source-derived complete native topologies."""
    try:
        roots = source["roots"]
        level = source["native_retained_container"]["level"]
        if (
            source.get("attachment_field") is not None
            or len(roots) != 1
            or type(roots[0]) is not int
            or roots[0] <= 0
            or type(level) is not int
            or not 0 <= level <= 32767
        ):
            return "hp_level_ordinary_source_unqualified"
        root = compiled.effects[str(roots[0])]
        if (
            not _metadata(root, registry, family=304, count=3, duration=-1, root=True)
            or root["children"]
            or tuple(root["parameters"])[1::2] != (0, 0, 0)
        ):
            return "hp_level_initial_root_unqualified"
        carrier_id, initial_level, chance = effect_profile(root, level)["parameters"]
        if not 0 < initial_level <= 100 or chance != -1:
            return "hp_level_initial_state_level_unqualified"
        carrier = compiled.source_states["states"][str(carrier_id)]
        members = tuple(carrier["effect_ids"])
        if len(members) != 5 or not _state(
            compiled.source_states, carrier_id, additive=True, effects=members
        ):
            return "hp_level_carrier_state_unqualified"
        markers, groups = members[:3], members[3:]
        for identity, bounds in zip(markers, ((0, 9), (10, 99), (100, 999))):
            marker = compiled.effects[str(identity)]
            if (
                not _metadata(
                    marker, registry, family=400, count=1, duration=-1, bounds=bounds
                )
                or marker["children"]
                or tuple(marker["parameters"]) != (0, 1)
            ):
                return "hp_level_marker_branch_unqualified"
        # Inclusive native min/max intervals exhaust the closed0..100 domain;
        # each boundary is checked, with no invented always-enabled markers.
        for rank in (0, 9, 10, 99, 100):
            marker = markers[0 if rank < 10 else 1 if rank < 100 else 2]
            if tuple(
                state_profile(compiled.source_states, carrier_id, rank)["effects"]
            ) != (marker, *groups):
                return "hp_level_carrier_level_branch_unqualified"
        secondary_id = None
        for ordinal, identity in enumerate(groups):
            group = compiled.effects[str(identity)]
            masks = (
                (None, None, None, (1, 2), None, (1001, 1002), None)
                if ordinal == 0
                else (None, None, None, None, None, (1003,), None)
            )
            if (
                not _metadata(
                    group,
                    registry,
                    family=1047,
                    count=11,
                    duration=-1,
                    masks=masks,
                    carrier=True,
                )
                or tuple(group["parameters"]) != _GROUP_RAW
                or len(group["children"]) != 2
            ):
                return "hp_level_exact_missing_percent_group_unqualified"
            remove, apply = (compiled.effects[str(key)] for key in group["children"])
            if (
                not _metadata(
                    remove, registry, family=321, count=1, duration=0, end=True
                )
                or not _metadata(
                    apply, registry, family=304, count=3, duration=0, end=True
                )
                or remove["children"]
                or apply["children"]
            ):
                return "hp_level_ordered_decurse_reapply_unqualified"
            state_id = effect_profile(apply, 0)["parameters"][0]
            if (
                tuple(remove["parameters"]) != (state_id, 0)
                or tuple(apply["parameters"]) != (state_id, 0, 0, 1, -1, 0)
                or (secondary_id is not None and secondary_id != state_id)
            ):
                return "hp_level_secondary_identity_unqualified"
            secondary_id = state_id
        secondary = compiled.source_states["states"][str(secondary_id)]
        leaves = tuple(secondary["effect_ids"])
        if len(leaves) != 1:
            return "hp_level_secondary_scalar_count_unqualified"
        leaf = compiled.effects[str(leaves[0])]
        family = leaf["effect_class"]
        row = registry["effects"].get(str(family), {})
        if (
            family not in (80, 120)
            or row.get("runner") != "eWQ"
            or row.get("dynamic_stat") is not False
            or type(row.get("fixed_stat_id")) is not int
            or row["fixed_stat_id"] != {80: 27, 120: 20}[family]
            or not _metadata(
                leaf, registry, family=family, count=1, duration=-1, end=True
            )
            or leaf["children"]
            or tuple(leaf["parameters"]) != (0, 1)
            or registry["effects"].get("400", {}).get("runner") != "eXE"
            or not _state(
                compiled.source_states,
                secondary_id,
                additive=family == 120,
                effects=leaves,
            )
        ):
            return "hp_level_secondary_scalar_contract_unqualified"
        for rank in (0, 100):
            if (
                tuple(
                    state_profile(compiled.source_states, secondary_id, rank)["effects"]
                )
                != leaves
            ):
                return "hp_level_secondary_level_branch_unqualified"
        return None
    except (KeyError, ValueError, TypeError, IndexError, AttributeError):
        return "hp_level_native_definition_incomplete"
