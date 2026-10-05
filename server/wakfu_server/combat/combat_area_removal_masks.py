"""aKa.ckD -> faV.rLR: event-removal masks, not actor fight properties."""


def area_removal_masks(definition):
    raw = definition.get("native_removal_masks", definition.get("properties"))
    if not isinstance(raw, (list, tuple)) or any(
        type(value) is not int or not 0 <= value < (1 << 31) for value in raw
    ):
        raise ValueError("Missing native faV removal-mask population")
    for alias in ("properties", "native_fight_properties"):
        if alias in definition and tuple(definition[alias]) != tuple(raw):
            raise ValueError("Native area removal-mask aliases disagree")
    return frozenset(raw)


def removal_mask_matches(definition, event_ids):
    if not isinstance(event_ids, (tuple, list, set, frozenset)) or any(
        type(value) is not int or not 0 <= value < (1 << 31) for value in event_ids
    ):
        raise ValueError("Actual native area source mask required")
    return bool(area_removal_masks(definition).intersection(event_ids))
