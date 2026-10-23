"""Definition-only permanent SELF/start/PA-scaled equipment qualification.

Application, native float32 group levels, PA bounds and actual-delta inverses
remain owned by the existing state, group and scalar combat runners. Identities
come from graph edges, never an equipment, state or effect allowlist.
"""
from collections.abc import Mapping
import math

from .combat_definitions import effect_profile, state_profile
from .combat_operation_registry import assess_operation

_HMI = frozenset(("rzc", "rzd", "rze", "rzf", "rzg", "rzh"))
_CLOCK = frozenset(
    ("clock_on_caster", "clock_on_target", "ryE", "ryF", "ryG", "ryH", "ryI", "esr")
)


def _metadata(
    effect,
    registry,
    *,
    family,
    count,
    duration,
    root=False,
    carrier=False,
    events=(),
    flags=None
):
    masks = effect["target_masks"]
    selector = effect["native_target_selector"]
    timing = effect["native_timing_definition"]
    hmi = effect["native_hmi_actions"]
    parameters = effect["parameters"]
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
        or (effect["minimum_level"], effect["maximum_level"]) != (0, 32767)
        or effect["native_execution_mode"] != (0 if root else 2)
        or effect["native_definition_class"] != ("eVE" if root else "eVy")
        or effect["area_class"] != ("anA" if root else "anD")
        or effect["area_native"] != ("empty" if root else "point")
        or not isinstance(selector, Mapping)
        or selector != {"class": "fcE", "mask": 0 if root else 1}
        or type(selector.get("mask")) is not int
        or (root and effect.get("native_active_effect") is not False)
        or effect["native_localization_enabled"] is not False
        or type(effect["criteria"]) is not str
        or effect["criteria"].strip()
        or not isinstance(parameters, (tuple, list))
        or len(parameters) != count * 2
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in parameters)
        or not isinstance(masks, (tuple, list))
        or len(masks) != 7
        or any(masks[i] for i in (0, 1, 2, 3, 4, 6))
        or any(
            row is not None
            and (
                not isinstance(row, (tuple, list))
                or any(type(v) is not int for v in row)
            )
            for row in masks
        )
        or tuple(masks[5] or ()) != events
        or tuple(effect["native_effect_flags"])
        != ((() if root or duration == 0 else (17,)) if flags is None else flags)
        or effect["application_flag"] != ("EFFECT_CARRIER" if carrier else "NONE")
        or effect["removal_flag"] != ("EFFECT_CARRIER" if carrier else "NONE")
        or effect["probability_base"] != 100
        or effect["probability_per_level"] != 0
        or not isinstance(hmi, Mapping)
        or set(hmi) != _HMI
        or any(not isinstance(rows, (tuple, list)) or rows for rows in hmi.values())
        or assess_operation(effect, characteristic_registry=registry).status
        != "conditional"
    ):
        return False
    if root:
        return timing == {"clock_on_caster": False, "clock_on_target": True}
    return (
        isinstance(timing, Mapping)
        and set(timing) == _CLOCK
        and timing["clock_on_caster"] is False
        and timing["clock_on_target"] is True
        and timing["esr"] is False
        and timing["ryG"] is False
        and type(timing["ryE"]) is int
        and timing["ryE"] == duration
        and all(
            type(timing[k]) in (int, float) and timing[k] == 0
            for k in ("ryF", "ryH", "ryI")
        )
    )


def _state(catalog, reference, members):
    definition = catalog["states"][str(reference)]
    if (
        type(definition["maximum_level"]) is not int
        or definition["maximum_level"] != 100
        or tuple(definition["effect_ids"]) != members
        or definition["duration_per_level"] != 0
        or definition["realtime_duration_per_level"] != 0
    ):
        return False
    for level in range(101):
        profile = state_profile(catalog, reference, level)
        if (
            profile["level"] != level
            or tuple(profile["effects"]) != members
            or profile["duration"] != -1
            or profile["realtime_duration"] != 0
            or profile["clock_actor"] != "target"
            or profile["tick_at_turn_end"] is not False
            or any(
                profile[k] is not False
                for k in (
                    "additive",
                    "replace",
                    "refresh",
                    "protected",
                    "skip_turn_timer",
                )
            )
        ):
            return False
    return True


def start_characteristic_state_contract(source, compiled, registry):
    """Return None only for the reviewed complete start-characteristic topology."""
    try:
        roots = source["roots"]
        level = source["native_retained_container"]["level"]
        omitted = source.get("unplanned_passive_effect_ids")
        if (
            source.get("attachment_field") is not None
            or len(roots) != 1
            or type(roots[0]) is not int
            or roots[0] <= 0
            or type(level) is not int
            or not 0 <= level <= 32767
            or not isinstance(omitted, (tuple, list))
            or omitted
        ):
            return "start_characteristic_ordinary_source_unqualified"
        effects = compiled.effects
        root = effects[str(roots[0])]
        if (
            not _metadata(root, registry, family=304, count=3, duration=-1, root=True)
            or root["children"]
            or tuple(root["parameters"])[1::2] != (0, 0, 0)
        ):
            return "start_characteristic_initial_root_unqualified"
        state_id, state_level, chance = effect_profile(root, level)["parameters"]
        if state_id <= 0 or not 0 < state_level <= 100 or chance != -1:
            return "start_characteristic_initial_level_unqualified"
        state = compiled.source_states["states"][str(state_id)]
        members = tuple(state["effect_ids"])
        if len(members) != 2 or not _state(compiled.source_states, state_id, members):
            return "start_characteristic_state_clock_or_topology_unqualified"
        marker, listener = (effects[str(ref)] for ref in members)
        if (
            not _metadata(marker, registry, family=400, count=2, duration=-1)
            or marker["children"]
            or tuple(marker["parameters"]) != (0, 1, 0, 3)
            or not _metadata(
                listener,
                registry,
                family=330,
                count=1,
                duration=-1,
                carrier=True,
                events=(1003,),
            )
            or tuple(listener["parameters"]) != (0, 0)
            or len(listener["children"]) != 2
            or len(set(listener["children"])) != 2
        ):
            return "start_characteristic_start_listener_unqualified"
        from .equipment_characteristics import native_rows
        from .combat_characteristic_level_group import characteristic_group_override

        rows = native_rows()
        selected_stats = set()
        for ordinal, reference in enumerate(listener["children"]):
            group = effects[str(reference)]
            raw = tuple(group["parameters"])
            if (
                not _metadata(
                    group,
                    registry,
                    family=913,
                    count=11,
                    duration=0,
                    flags=(() if ordinal == 0 else (17,)),
                )
                or len(group["children"]) != 4
                or len(set(group["children"])) != 4
                or raw[:12] != (0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0)
                or raw[13:] != (0, 0, 0, 0, 0, 0, 0.01, 0, 0)
                or raw[12] != int(raw[12])
            ):
                return "start_characteristic_pa_group_unqualified"
            stat = int(raw[12])
            row = rows.get(stat)
            if (
                not 0 < stat <= 255
                or row is None
                or row["expandable"]
                or row["frozen"]
                or stat in (1, 2, 3, 4)
                or any(type(row[k]) is not int for k in ("minimum", "maximum"))
                or not -(1 << 31) <= row["minimum"] <= row["maximum"] < (1 << 31)
                or stat in selected_stats
            ):
                return "start_characteristic_selected_pa_unqualified"
            selected_stats.add(stat)
            child_levels = {0, 32767}
            for rank in range(101):
                for current in (row["minimum"], row["maximum"]):
                    child_level = characteristic_group_override(
                        group,
                        rank,
                        current=current,
                        maximum=row["maximum"],
                        return_native_override=True,
                    )
                    if type(child_level) is not int or not -(1 << 31) <= child_level < (
                        1 << 31
                    ):
                        return "start_characteristic_child_level_bounds_unqualified"
                    # Native eYn passes an int override; the ordered group
                    # narrows it to short, except -1 keeps its inherited level.
                    child_levels.add(
                        rank
                        if child_level == -1
                        else ((child_level + 32768) % 65536) - 32768
                    )
            output_stats, reductions = set(), 0
            for child in group["children"]:
                leaf = effects[str(child)]
                family = leaf["effect_class"]
                scalar = registry["effects"].get(str(family), {})
                pc = scalar.get("fixed_stat_id")
                target = rows.get(pc)
                if (
                    not _metadata(leaf, registry, family=family, count=2, duration=-1)
                    or leaf["children"]
                    or scalar.get("runner") not in ("eWQ", "eWR")
                    or scalar.get("dynamic_stat") is not False
                    or type(pc) is not int
                    or not 0 < pc <= 255
                    or pc in (1, 2, 3, 4)
                    or pc in output_stats
                    or target is None
                    or target["expandable"]
                    or target["frozen"]
                    or tuple(leaf["parameters"])[::2] != (0, 0)
                    or leaf["parameters"][3] != 0
                    or leaf["parameters"][1]
                    != (3 if scalar.get("runner") == "eWR" else 1)
                ):
                    return "start_characteristic_scalar_leaf_unqualified"
                output_stats.add(pc)
                reductions += scalar["runner"] == "eWR"
                for child_level in child_levels:
                    if child_level < 0:
                        continue  # Native min-level0 excludes this invocation.
                    values = effect_profile(leaf, child_level)["parameters"]
                    if (
                        len(values) != 2
                        or values[1] != 0
                        or not 0 <= values[0] < (1 << 31)
                    ):
                        return "start_characteristic_scalar_amount_unqualified"
            if reductions != 1:
                return "start_characteristic_scalar_inverse_topology_unqualified"
        return None
    except (KeyError, TypeError, ValueError, IndexError, OverflowError):
        return "start_characteristic_incomplete_or_unknown_definition"
