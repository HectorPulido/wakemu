"""Source-bound non-characteristic gear roles for the fresh combat snapshot.

State installation belongs to Ready. Native relic aura400 remains a graphical
source; recognizing its zero static contribution does not execute or erase its
conditions, subscriptions, packets or native particle actions.
"""
from .combat_character_copy_equipment import native_copied_equipment_catalog
from .combat_copied_equipment_plan import copied_equipment_plan
from .combat_equipment_initialization import plan
from .combat_owned_equipment import compiled_with_sources, ordinary_turn_state_contract
from .combat_static_catalogs import characteristic_registry


def _relic_aura(root):
    metadata = root["metadata"]
    actions = metadata.get("native_hmi_actions")
    if (
        root["effect_class"] != 400
        or root["parameter_count"] != 0
        or root["parameters"] != []
        or root["children"] != []
        or root["variant"] != 0
        or metadata.get("native_active_effect") is not False
        or metadata.get("native_effect_flags") != [35]
        or metadata.get("native_execution_mode") != 0
        or metadata.get("native_definition_class") != "eVE"
        or metadata.get("application_flag") != "NONE"
        or metadata.get("removal_flag") != "NONE"
        or not isinstance(actions, dict)
    ):
        return False
    rows = [action for group in actions.values() for action in group]
    # Original eVl flag35=IS_RELIC_AURA; eXE null calculation has no
    # characteristic. Retain only source-described particle-only visuals.
    return bool(rows) and all(
        action.get("type") == "PARTICLE_SYSTEM"
        and action.get("aYc") is False
        and action.get("aYd") is False
        for action in rows
    )


def snapshot_roles(character, unsupported):
    """Return exact (inventory UID, item reference, root ID, family) ownership roles.

    Unknown roots stay rejected by the caller. No passive is executed here,
    and no characteristic or equipment serializer is changed.
    """
    relevant = [
        row
        for row in unsupported
        if isinstance(row, dict)
        and row.get("reason") == "unsupported-native-effect"
        and row.get("generic") in (304, 400)
    ]
    if not relevant:
        return {}
    sources = plan(character, ordinary_only=True)
    roles = {}
    if any(row["generic"] == 304 for row in relevant):
        from .combat_server_spell import compiled_runtime_catalog

        compiled = compiled_with_sources(compiled_runtime_catalog(), sources)
        registry = characteristic_registry()
        for source in sources:
            if ordinary_turn_state_contract(source, compiled, registry) is None:
                for reference in source["roots"]:
                    roles[
                        (source["uid"], source["reference"], reference, 304)
                    ] = "qualified-ready-state"
    if any(row["generic"] == 400 for row in relevant):
        native = native_copied_equipment_catalog()
        items = {row["uid"]: row for row in character.get("inventory_items", [])}
        for row in relevant:
            if row["generic"] != 400:
                continue
            gear = items.get(row["uid"])
            if gear is None or gear["reference"] != row["reference"]:
                continue
            source = copied_equipment_plan(gear["reference"], native)
            for root in source["roots"]:
                if root["reference"] == row["effect_id"] and _relic_aura(root):
                    roles[
                        (row["uid"], row["reference"], row["effect_id"], 400)
                    ] = "native-relic-aura-no-static-characteristic"
    return roles
