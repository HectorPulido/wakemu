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
from functools import lru_cache


from .combat_equipment_root_roles import relic_aura as _relic_aura


@lru_cache(maxsize=None)
def native_relic_aura(reference, effect_reference):
    """Qualify an original particle-only root without rebuilding equipment."""
    source = copied_equipment_plan(reference, native_copied_equipment_catalog())
    return any(
        root["reference"] == effect_reference and _relic_aura(root)
        for root in source["roots"]
    )


def prestart_state_roles(character, entries, unsupported):
    """Recognize event-only states before they can change any scalar PA.

    Entries come from the physical ownership/slot validator. Only the specific
    start-characteristic, movement/trigger or start-heal topology is statically neutral here; a generic Ready
    state may apply immediate scalar effects and must not be treated as zero.
    Original source rows remain available to the normal Ready installer.
    """
    if not any(row.get("generic") == 304 for row in unsupported):
        return {}
    from .combat_equipment_start_characteristic_contract import (
        start_characteristic_state_contract,
    )
    from .combat_equipment_reactive_trigger_contract import (
        reactive_trigger_state_contract,
    )
    from .combat_equipment_opposed_damage_contract import opposed_damage_state_contract
    from .combat_equipment_start_heal_contract import start_heal_state_contract
    from .combat_equipment_start_hp_scalar_contract import (
        start_hp_scalar_state_contract,
    )
    from .combat_server_spell import compiled_runtime_catalog

    sources = plan(character, ordinary_only=True, _selected_entries=entries)
    compiled = compiled_with_sources(compiled_runtime_catalog(), sources)
    registry = characteristic_registry()
    roles = {}
    for source in sources:
        if not source.get("unplanned_passive_effect_ids") and (
            start_characteristic_state_contract(source, compiled, registry) is None
            or reactive_trigger_state_contract(source, compiled, registry) is None
            or opposed_damage_state_contract(source, compiled, registry) is None
            or start_heal_state_contract(source, compiled, registry) is None
            or start_hp_scalar_state_contract(source, compiled, registry) is None
        ):
            for reference in source["roots"]:
                roles[
                    (source["uid"], source["reference"], reference, 304)
                ] = "qualified-event-state"
    return roles


def snapshot_roles(character, unsupported):
    """Return exact (inventory UID, item reference, root ID, family) ownership roles.

    Unknown roots stay rejected by the caller. No passive is executed here,
    and no characteristic or equipment serializer is changed.
    """
    relevant = [
        row
        for row in unsupported
        if isinstance(row, dict) and row.get("reason") == "unsupported-native-effect"
    ]
    if not relevant:
        return {}
    sources = plan(character, ordinary_only=True)
    roles = {}
    sources_by_uid = {source["uid"]: source for source in sources}
    # Only roots retained by the shared non-snapshot classifier may defer their
    # contribution to Ready. The later complete-graph capability assessment and
    # actual factory binding verification still own execution authorization.
    for row in relevant:
        if row.get("generic") == 304:
            continue  # Preserve the existing state-specific role labels below.
        source = sources_by_uid.get(row.get("uid"))
        if (
            source is None
            or source.get("reference") != row.get("reference")
            or row.get("effect_id") not in source.get("roots", ())
        ):
            continue
        effect = source["effects"].get(str(row["effect_id"]))
        if effect is not None and effect.get("effect_class") == row.get("generic"):
            roles[
                (row["uid"], row["reference"], row["effect_id"], row["generic"])
            ] = "deferred-owned-operator-ready-owned"
    if any(row["generic"] == 304 for row in relevant):
        from .combat_server_spell import compiled_runtime_catalog

        compiled = compiled_with_sources(compiled_runtime_catalog(), sources)
        registry = characteristic_registry()
        sources_by_uid = {source["uid"]: source for source in sources}
        for source in sources:
            if ordinary_turn_state_contract(source, compiled, registry) is None:
                for reference in source["roots"]:
                    roles[
                        (source["uid"], source["reference"], reference, 304)
                    ] = "qualified-ready-state"
        # A family-304 root has no static characteristic contribution: it is
        # registered by the owned-equipment Ready transaction. This role only
        # lets the fresh actor snapshot omit that deferred contribution; it
        # does not authorize the graph to execute. The later prepare step still
        # requires either the exact legacy contract above or a live generic
        # operation/provider assessment, and pin/initialization recheck the
        # runtime factory routes before applying it.
        for row in relevant:
            if row["generic"] != 304:
                continue
            source = sources_by_uid.get(row.get("uid"))
            if (
                source is None
                or source.get("reference") != row.get("reference")
                or row.get("effect_id") not in source.get("roots", ())
            ):
                continue
            root = compiled.effects.get(str(row["effect_id"]))
            if root is not None and root.get("effect_class") == 304:
                roles.setdefault(
                    (row["uid"], row["reference"], row["effect_id"], 304),
                    "deferred-owned-state-no-static-characteristic",
                )
    if any(row["generic"] in (400, 449) for row in relevant):
        native = native_copied_equipment_catalog()
        items = {row["uid"]: row for row in character.get("inventory_items", [])}
        for row in relevant:
            if row["generic"] not in (400, 449):
                continue
            gear = items.get(row["uid"])
            if gear is None or gear["reference"] != row["reference"]:
                continue
            source = copied_equipment_plan(gear["reference"], native)
            from .combat_equipment_direct_marker_contract import direct_marker_root

            for root in source["roots"]:
                if root["reference"] == row["effect_id"] and (
                    _relic_aura(root) or direct_marker_root(root)
                ):
                    roles[
                        (row["uid"], row["reference"], row["effect_id"], row["generic"])
                    ] = (
                        "native-relic-aura-no-static-characteristic"
                        if _relic_aura(root)
                        else "native-owned-null-marker-no-static-characteristic"
                    )
    return roles
