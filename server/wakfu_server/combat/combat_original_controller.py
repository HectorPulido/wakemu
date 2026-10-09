"""eKc -> Qe.bbc -> eHg.dTD, never the event source/rebound actor."""
from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS

CURRENT_TARGET = object()


def original_target_controller(preview, actor_authority, identity):
    if identity is None:
        return 0  # Qe.bbc is explicitly null.
    if type(identity) is not int:
        raise ValueError("Missing native original target identity")
    from .combat_native_actor_lookup import native_actor

    actor = native_actor(preview, identity)
    if actor is not None:
        value = actor_authority(preview, actor).native_controller_id
    else:
        areas = getattr(preview, "native_effect_areas", {})
        retired = getattr(preview, "native_retired_area_managers", {})
        row = areas.get(identity, retired.get(identity))
        if (
            not isinstance(row, dict)
            or row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
        ):
            raise ValueError("Unknown native original target PV/eHg authority")
        if "owner_id" not in row:
            raise ValueError("Missing native faV.bgZ owner presence")
        value = row["owner_id"]
        if value is None:
            value = 0  # faV.dTD explicitly returns0 for null bgZ.
    if type(value) is not int or not -(1 << 63) <= value < (1 << 63):
        raise ValueError("Missing native original target controller dTD")
    return value


def controller_predicate(
    preview, actor_authority, caster_id, target_id, cell, *, target_is_cell, name
):
    """eIC/eOx compare actual eHg.dTD with selected eHg.dTD or PV.Sn."""
    from .combat_qi_fight import current_registry
    from .combat_global_pv_collections import global_pv_iterator
    from .combat_effect_area_geometry import contains_area_cell

    source = preview.actors.get(caster_id)
    if source is None:
        raise ValueError("Original-controller predicate requires actual caster eHg")
    if actor_authority(preview, source).targeting.get("is_eGj") is not True:
        raise ValueError("Missing actual original-controller caster eHg type")
    original = original_target_controller(preview, actor_authority, caster_id)
    areas = getattr(preview, "native_effect_areas", {})
    selected = []
    if target_is_cell or target_id is None:
        if cell is None:
            return False
        registry = current_registry(preview)
        for slot in registry.ordered_U(*cell[:2]):
            row = registry.slots[slot]
            if row is None or row["identity"][0] != "actor":
                continue
            actor = preview.actors[row["identity"][1]]
            if actor_authority(preview, actor).targeting.get("is_eGj") is not True:
                raise ValueError("Missing actual original-controller target eHg type")
            selected.append(actor.id)
            break
        # eII.n materializes Qs.f before comparing any candidates.
        order = global_pv_iterator(preview, caster_id=None, caster_only=False)
        for identity in order:
            row = areas.get(identity)
            if row is not None and contains_area_cell(row, cell):
                if row.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS:
                    raise ValueError(
                        "Unsupported actual Qs original-controller eHg type"
                    )
                selected.append(identity)
    elif target_id in preview.actors:
        if (
            actor_authority(preview, preview.actors[target_id]).targeting.get("is_eGj")
            is not True
        ):
            raise ValueError("Missing actual original-controller target eHg type")
        selected.append(target_id)
    elif target_id in areas:
        if areas[target_id].get("native_area_contract") in SUPPORTED_AREA_CONTRACTS:
            selected.append(target_id)
        else:
            return False  # Actual non-eHg PV, no ePy/ePH context wrapper.
    else:
        raise ValueError("Missing actual original-controller target identity")
    if name == "IsOriginalController":
        return any(identity == original for identity in selected)
    if name == "CasterAndTargetHaveSameOriginalController":
        return any(
            original_target_controller(preview, actor_authority, identity) == original
            for identity in selected
        )
    raise ValueError("Unknown original-controller predicate")
