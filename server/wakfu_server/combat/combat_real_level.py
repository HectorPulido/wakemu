"""GetRealLevel eLc/eQb73: eGj.drm, distinct from modulated cmZ.

biB.drm reads progression fCo.cmZ; biB.cmZ reads selected eQW.eFZ.
NPC eGj.drm defaults to cmZ. The eventTarget selector uses native event
context, which callers must attest separately; missing facts never default.
"""


def native_real_level(context, argument=None):
    if argument is not None and type(argument) is not str:
        raise ValueError("Native GetRealLevel requires a string selector")
    selector = (
        "eventTarget"
        if argument == "eventTarget"
        else "target"
        if argument is not None and argument.lower() == "target"
        else "caster"
    )
    actor = context.actors.get(selector)
    if actor is None:
        raise ValueError("Missing authoritative GetRealLevel actor: " + selector)
    if actor.is_native_fighter is False:
        return -1  # eLc rejects actors which are not eGj.
    if actor.is_native_fighter is not True:
        raise ValueError("Missing native eGj type for GetRealLevel")
    value = actor.real_level
    if type(value) is not int or not -32768 <= value < 32768:
        raise ValueError("Missing authoritative native drm real level")
    return value
