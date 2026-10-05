"""Original eOZ: actual source REP34 and eVo.aZY, never listener category."""


def indirect_trigger(context):
    from .combat_conditions import UnknownCondition

    if context.triggering_effect_present is False:
        return False
    if context.triggering_effect_present is not True:
        raise UnknownCondition("Missing actual native triggering effect")
    flags = context.triggering_effect_flags
    if flags is None:
        raise UnknownCondition("Missing native triggering definition flags")
    if 34 in flags:
        return False
    kind = context.triggering_container_type
    if type(kind) is not int:
        raise UnknownCondition("Missing actual triggering eVo.aZY")
    # Original eOZ null PL returns -1; eIX maps -1 to false.
    return kind not in (0, 11, 12)
