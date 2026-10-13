"""fbX.aE: retire only displaced, owner-linked faY zones during carrying."""


def carried_glyphs(fight, actor):
    from .combat_effect_area import native_effect_areas
    from .combat_parameters import _float32

    selected = []
    for row in fight.native_effect_areas.values():
        if row.get("native_area_contract") != "faY" or row.get("owner_id") != actor.id:
            continue
        definition = native_effect_areas()[str(row["reference"])]
        parameters = definition.get("raw_bdh")
        if not isinstance(parameters, (tuple, list)):
            raise ValueError("Missing native faY constructor parameters")
        # aQc sets rMq from parameter0 == 1. fTC returns true when rMq
        # is false; otherwise it compares the saved reference to the owner.
        if not parameters or _float32(parameters[0]) != 1:
            continue
        reference = row.get("native_geometry_reference")
        if not isinstance(reference, (tuple, list)) or len(reference) != 3:
            raise ValueError("Missing native faY reference coordinates")
        if tuple(reference) != tuple(actor.position):
            selected.append(row)
    return tuple(selected)


def cleanup_carried_glyphs(fight, actor, *, callbacks):
    from .combat_effect_area import remove_owned_hour_area

    rows = carried_glyphs(fight, actor)
    if rows and callbacks is None:
        raise ValueError("Missing actual Qs carrying cleanup callbacks")
    for row in rows:
        # Native Qs.b unregisters the area, not its parent runner. The
        # evaluated carry packet performs the same cleanup on the client.
        remove_owned_hour_area(fight, row["uid"], callbacks=callbacks)
    return rows
