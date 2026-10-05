"""eQb349 -> ePa -> eYE.b: source REP23/24 and actual PV radii."""


def melee_trigger(context):
    from .combat_conditions import UnknownCondition

    if context.triggering_effect_present is False:
        return False  # ePa null running effect returns -1 (false).
    if context.triggering_effect_present is not True:
        raise UnknownCondition("Missing actual native triggering effect")
    flags = context.triggering_effect_flags
    if flags is None:
        raise UnknownCondition("Missing native triggering definition flags")
    if 23 in flags:
        return True
    if 24 in flags:
        return False
    distance = context.triggering_melee_distance
    if type(distance) is not int or distance < 0:
        raise UnknownCondition(
            "Missing actual source melee distance and physical radii"
        )
    return distance <= 2
