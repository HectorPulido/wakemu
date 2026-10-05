"""Original eVi runner masks; collision204 is a separate native caller."""
BASE_EVENT_IDS = {
    300: (0, 185, 187),  # eXK, parent eXD
    305: (0, 185, 193),  # eXq, parent eXD
    301: (0, 185, 188),  # eXJ, parent eXD
    331: (0, 185, 194),  # eXp, parent eXD
    302: (0, 189, 197),  # eZC, parent eZB
    340: (0, 189, 198),  # eZD, parent eZB
    422: (0, 184),  # eXk
}


def displacement_event_ids(effect):
    kind = effect["effect_class"]
    if type(kind) is not int or kind not in BASE_EVENT_IDS:
        raise ValueError("Audited native displacement runner required")
    masks = effect["target_masks"]
    if len(masks) != 7 or any(type(n) is not int or n < 0 for n in masks[6] or ()):
        raise ValueError("Native displacement definition event masks required")
    return tuple(sorted({*BASE_EVENT_IDS[kind], *(masks[6] or ())}))
