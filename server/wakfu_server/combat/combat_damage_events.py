"""Audited eXt.bbx/fOG and post-consumption fOF event production.

Delivery phases are Qe.L channels, not event IDs. Death/turn/state lifecycle
notifications are distinct native callers and are deliberately not fabricated.
"""
ELEMENT_EVENT_IDS = {1: None, 2: 5, 3: 8, 4: 6, 5: 7}
FLAG_EVENT_IDS = {4: 2215, 22: 2216, 23: 2218, 24: 2217}


def damage_event_ids(
    effect, *, container_type, phase, blocked, localization, context_is_native_fight
):
    """Return exact events for an eXt source with an unchanged native element.

    fau may select a different element on other execution contexts; callers
    must project that actual source family instead of using an unverified one.
    Block notification2233 exists only after c() on eVw native fight contexts.
    Back notification29 follows Sl.o regardless of arithmetic-localization flag.
    """
    kind = effect["effect_class"]
    if kind not in ELEMENT_EVENT_IDS or type(kind) is not int:
        raise ValueError("Native eXt element family required")
    if phase not in (1, 2, 3, 4) or type(phase) is not int:
        raise ValueError("Audited native damage phase required")
    if container_type is not None and type(container_type) is not int:
        raise ValueError("Explicit native container type required")
    if type(blocked) is not bool or type(context_is_native_fight) is not bool:
        raise ValueError("Native block and fight context required")
    if localization not in ("FRONT", "SIDE", "BACK"):
        raise ValueError("Actual native Sl.o localization required")
    flags = effect["native_effect_flags"]
    masks = effect["target_masks"]
    if len(masks) != 7 or any(type(flag) is not int for flag in flags):
        raise ValueError("Native source flags/masks required")
    events = {0, 2, *(masks[6] or ())}
    element = ELEMENT_EVENT_IDS[kind]
    if element is not None:
        events.add(element)
    events.update(event for flag, event in FLAG_EVENT_IDS.items() if flag in flags)
    # eXt.fOG: flag34 overrides; absent container or any kind except11/12 is indirect.
    if 34 not in flags and container_type not in (11, 12):
        events.add(2268)
    if phase in (3, 4):
        if blocked and context_is_native_fight:
            events.add(2233)
        if localization == "BACK":
            events.add(29)
    return tuple(sorted(events))
