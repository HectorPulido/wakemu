"""eKc -> Qe.bbc -> eHg.dTD, never the event source/rebound actor."""
CURRENT_TARGET = object()


def original_target_controller(preview, actor_authority, identity):
    if identity is None:
        return 0  # Qe.bbc is explicitly null.
    if type(identity) is not int:
        raise ValueError("Missing native original target identity")
    actor = preview.actors.get(identity)
    if actor is not None:
        value = actor_authority(preview, actor).native_controller_id
    else:
        areas = getattr(preview, "native_effect_areas", {})
        retired = getattr(preview, "native_retired_area_managers", {})
        row = areas.get(identity, retired.get(identity))
        if not isinstance(row, dict) or row.get("native_area_contract") not in (
            "faY",
            "faZ",
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
