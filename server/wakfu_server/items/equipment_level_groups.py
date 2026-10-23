"""Whole-source static ordinary eYm groups, with explicit actor/config authority.

Snapshot ownership replaces each qualified ordered group with its native leaf
operations. Nothing is installed again at Ready. State/event groups retain
ordinary combat ownership and are deliberately outside this static contract.
"""
from functools import lru_cache
import math


def _criterion(root):
    value = root.get("criterion_raw")
    return "" if value is None and root.get("criterion_native") is None else value


def _metadata(root, *, profession=False, explicit_self=False):
    m = root.get("metadata", {})
    return (
        root.get("variant") == 0
        and m.get("native_active_effect") is False
        and m.get("native_definition_class") == "eVE"
        and m.get("native_execution_mode") == 0
        and m.get("native_timing_definition")
        == {"clock_on_caster": False, "clock_on_target": True}
        and m.get("target_masks") == [None] * 7
        # Original eHi explicitly supplies the equipped owner as target. This
        # exact point contains only that owner; fcE1 is VALID_IF_IN_AOE, not a
        # generic SELF flag. The ordered group transmits that same target,
        # without actor rebinding or a cell/area expansion.
        and m.get("native_target_selector")
        == {"class": "fcE", "mask": 0 if explicit_self else 1}
        and (
            (m.get("area_native"), m.get("area_class")) == ("point", "anD")
            or (profession or explicit_self)
            and (m.get("area_native"), m.get("area_class")) == ("empty", "anA")
        )
        and m.get("native_effect_flags") == []
        and m.get("native_localization_enabled") is False
        and m.get("application_flag") == "NONE"
        and m.get("removal_flag") == "NONE"
        and m.get("probability_base") == 100
        and m.get("probability_per_level") == 0
        and isinstance(m.get("native_hmi_actions"), dict)
        and set(m["native_hmi_actions"]) == {"rzc", "rzd", "rze", "rzf", "rzg", "rzh"}
        and not any(m["native_hmi_actions"].values())
        and _criterion(root) in ("", "IsNeoServer()")
        and type(root.get("minimum_level")) is int
        and root["minimum_level"] == 0
        and type(root.get("maximum_level")) is int
        and root["maximum_level"] == 32767
        and type(root.get("parameter_count")) is int
        and isinstance(root.get("parameters"), list)
        and len(root["parameters"]) == root["parameter_count"] * 2
        and all(
            type(v) in (int, float) and math.isfinite(v) for v in root["parameters"]
        )
        and root.get("children")
        == [row.get("reference") for row in root.get("child_definitions", ())]
    )


def _leaf_kind(root, registry):
    """Resolve actual eVi characteristic bindings; no invented generic IDs."""
    from wakfu_server.combat_maximum_resource import FAMILIES
    from wakfu_server.equipment_characteristics import native_rows

    kind, raw = root["effect_class"], root["parameters"]
    row = registry["effects"].get(str(kind), {})
    if root["children"]:
        return None
    if row.get("runner") == "eWQ" and root["parameter_count"] == 1:
        stat = row.get("fixed_stat_id")
        native = native_rows().get(stat)
        if (
            row.get("percent_default") is False
            and row.get("limit_policy") == "NORMAL"
            and row.get("limit_policy_requires_owned_stack") is False
            and native is not None
            and native["expandable"] is False
            and native["frozen"] is False
            and all(value >= 0 for value in raw)
        ):
            return "scalar", stat
    # Maximum-resource families have their own audited registry/handler;
    # they are intentionally absent from the current-stat registry above.
    if (
        kind in FAMILIES
        and FAMILIES[kind][0] in (1, 2, 3, 4)
        and root["parameter_count"] == 3
        and raw[2:] == [1, 0, 0, 0]
        and raw[0] >= 0
        and raw[1] >= 0
    ):
        return "maximum", FAMILIES[kind][0]
    return None


def qualify_plan(plan, summaries, registry):
    """Return a concrete reason unless every ordinary passive root is covered."""
    from wakfu_server.profession_equipment_modifiers import passive_profession_effect

    identities = {row["id"]: row for row in summaries}
    found_group = False
    seen = set()
    # A mixed reactive source must qualify its entire state closure before
    # accepting the original explicit-target fcE0 scalar/group metadata.
    state_roots = [r for r in plan["roots"] if r["effect_class"] == 304]
    explicit_self = False
    if state_roots:
        from wakfu_server.combat_equipment_opposed_damage_contract import (
            copied_opposed_damage_root,
        )

        if len(state_roots) != 1 or not copied_opposed_damage_root(
            state_roots[0], plan["native_retained_container"]
        ):
            return "level_group_reactive_sibling_unqualified"
        explicit_self = True

    def visit(root, *, nested=False):
        nonlocal found_group
        summary = identities.get(root.get("reference"))
        profession = (
            not nested
            and summary is not None
            and not root.get("children")
            and not root.get("child_definitions")
            and passive_profession_effect(summary, plan["reference"])
        )
        if root.get("reference") in seen or not _metadata(
            root, profession=profession, explicit_self=explicit_self
        ):
            return "level_group_metadata_or_graph_unqualified"
        seen.add(root["reference"])
        if root["effect_class"] == 999:
            found_group = True
            p = root["parameters"]
            if (
                root["parameter_count"] != 8
                or p[:12] != [0, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
                or p[12] not in (0, 1)
                or p[13] != 0
                or p[14] <= 0
                or p[15] != 0
                or not root["children"]
            ):
                return "level_group_order_or_level_variant_unqualified"
            for child in root["child_definitions"]:
                reason = visit(child, nested=True)
                if reason:
                    return reason
            return None
        if _leaf_kind(root, registry) is not None:
            return None
        if profession:
            return None
        return "level_group_descendant_or_sibling_unqualified"

    for root in plan["roots"]:
        summary = identities.get(root["reference"])
        if (
            summary is None
            or summary.get("generic") != root.get("effect_class")
            or summary.get("params") != root.get("parameters")
            or summary.get("native_variant") != root.get("variant")
            or summary.get("effect_criteria") is not bool(_criterion(root))
            or summary.get("native_active_effect")
            is not root.get("metadata", {}).get("native_active_effect")
        ):
            return "level_group_complete_source_identity_required"
        if summary["native_variant"] != 0 or summary["native_active_effect"]:
            continue
        if explicit_self and root["effect_class"] == 304:
            continue  # Complete reactive closure remains Ready-owned.
        reason = visit(root)
        if reason:
            return reason
    return None if found_group else "level_group_source_has_no_group"


@lru_cache(maxsize=None)
def qualified_source(reference):
    from wakfu_server.equipment_stats import CATALOG

    summary = CATALOG.get(reference)
    if summary is None or not any(row["generic"] == 999 for row in summary["effects"]):
        return None
    from wakfu_server.combat_character_copy_equipment import (
        native_copied_equipment_catalog,
    )
    from wakfu_server.combat_copied_equipment_plan import copied_equipment_plan
    from wakfu_server.combat_static_catalogs import characteristic_registry

    plan = copied_equipment_plan(reference, native_copied_equipment_catalog())
    if qualify_plan(plan, summary["effects"], characteristic_registry()) is not None:
        return None
    return plan


def snapshot_root(reference, effect_id):
    source = qualified_source(reference)
    return source is not None and any(
        row["reference"] == effect_id and row["effect_class"] != 304
        for row in source["roots"]
    )


def project(reference, *, actor_level, container_level, criterion_context):
    """Return None for other/unqualified sources, otherwise exact ordered leaves."""
    source = qualified_source(reference)
    if source is None:
        return None
    if type(actor_level) is not int or not 1 <= actor_level <= 32767:
        raise ValueError("Missing native level-group effective actor level")
    if container_level is None:
        container_level = source["native_retained_container"]["level"]
    if type(container_level) is not int or not 0 <= container_level <= 32767:
        raise ValueError("Missing native level-group container level")
    from wakfu_server.equipment_stats import CATALOG
    from wakfu_server.combat_level_group import level_group_override
    from wakfu_server.combat_parameters import parameter_value
    from wakfu_server.combat_static_catalogs import characteristic_registry

    registry = characteristic_registry()
    summaries = {row["id"]: row for row in CATALOG[reference]["effects"]}
    rows = []

    def visit(root, level):
        if root["effect_class"] == 304:
            rows.append(dict(summaries[root["reference"]]))
            return  # Keep the native root for normal Ready installation.
        criterion = _criterion(root)
        if criterion:
            if (
                not isinstance(criterion_context, dict)
                or type(criterion_context.get("is_neo_server")) is not bool
            ):
                raise ValueError("Missing authoritative equipment Neo server mode")
            if not criterion_context["is_neo_server"]:
                return
        if root["effect_class"] == 999:
            definition = dict(parameters=root["parameters"])
            child_level = level_group_override(definition, level, actor_level)
            if not 0 <= child_level <= 32767:
                raise ValueError(
                    "Native equipment group child level is outside static domain"
                )
            for child in root["child_definitions"]:
                visit(child, child_level)
            return
        kind = _leaf_kind(root, registry)
        if kind is None:
            # The independently source-bound profession provider owns this row.
            rows.append(dict(summaries[root["reference"]]))
            return
        family, stat = kind
        values = [
            parameter_value(root["parameters"], i, level)
            for i in range(root["parameter_count"])
        ]
        if any(value < 0 for value in values):
            raise ValueError("Native equipment group amount outside static contract")
        row = dict(summaries.get(root["reference"], {}))
        row.update(
            id=root["reference"],
            generic=root["effect_class"],
            runner="eWN" if family == "maximum" else "eWQ",
            params=list(root["parameters"]),
            parameter_count=root["parameter_count"],
            stat_id=stat,
            stat_limit=-1,
            values=values,
            effect_criteria=False,
            has_triggers=False,
            target_mask=0,
            native_variant=0,
            native_active_effect=False,
            _native_level_group=True,
        )
        rows.append(row)

    for root in source["roots"]:
        if root["variant"] != 0 or root["metadata"]["native_active_effect"]:
            rows.append(dict(summaries[root["reference"]]))
        else:
            visit(root, container_level)
    return rows
