"""One ownership decision for native passive equipment root initialization.

Snapshot-owned scalars, professions and ordered static groups are never
executed a second time by Ready. Every remaining passive root keeps native
order and must pass the normal runtime capability and pinning gates.
"""


def relic_aura(root):
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


def root_role(reference, root, identity):
    """Classify complete native source metadata, without item/family allowlists."""
    if (
        type(identity.get("native_variant")) is not int
        or type(identity.get("native_active_effect")) is not bool
    ):
        raise ValueError("Missing complete native passive root identity")
    if identity["native_variant"] != 0 or identity["native_active_effect"]:
        return "separate-item-action"
    if root["effect_class"] == 304:
        return "runtime-operator"  # State installation remains owned by Ready.
    from .combat_equipment_direct_marker_contract import direct_marker_root

    if direct_marker_root(root):
        return "runtime-operator"
    from wakfu_server.equipment_level_groups import snapshot_root
    from wakfu_server.equipment_stats import (
        _flat,
        passive_null_marker,
        inactive_passive_root,
    )
    from wakfu_server.profession_equipment_modifiers import passive_profession_effect

    if snapshot_root(reference, root["reference"]):
        return "snapshot-ordered-group"
    from wakfu_server.equipment_hp_bonuses import descriptor as hp_descriptor

    if hp_descriptor(identity) is not None:
        return "snapshot-owned-hp"
    if _flat(identity) is not None:
        return "snapshot-characteristic"
    if passive_profession_effect(identity, reference):
        return "snapshot-profession"
    if identity["generic"] in (1068, 1069):
        return "snapshot-selected-element"
    if (
        passive_null_marker(identity)
        or inactive_passive_root(reference, identity)
        or relic_aura(root)
    ):
        return "snapshot-neutral"
    return "runtime-operator"
