"""Native fyF/eHl/fcj range calculation over explicit live authority."""
from .combat_conditions import UnknownCondition


def int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def effective_range(minimum, maximum, modifiable, bonus, carried, capped):
    """fcj.a(PV,boolean,int,int), after category modifiers in fyF.i."""
    if any(type(value) is not int for value in (minimum, maximum, bonus)) or any(
        type(value) is not bool for value in (modifiable, carried, capped)
    ):
        raise UnknownCondition("Incomplete native range authority")
    if maximum >= 1 and modifiable:
        bonus = int32(bonus + int(carried))
        maximum = max(minimum, int32(maximum + bonus))
    if capped and maximum > 1:
        maximum = 1
    return minimum, maximum


def resolve_range(rule, actor, context):
    """Read live RANGE, category range modifiers and native fight property2."""
    caster = getattr(context, "actors", {}).get("caster")
    properties = getattr(caster, "fight_properties", None)
    if properties is None:
        raise UnknownCondition("Missing native casting fight-property snapshot")
    modifiers = getattr(actor, "spell_range_modifiers", None)
    if not isinstance(modifiers, dict) or any(
        type(key) is not int or type(value) is not int
        for key, value in modifiers.items()
    ):
        raise UnknownCondition("Missing complete native eHl range modifier snapshot")
    maximum = rule["maximum"]
    for category in rule["categories"]:
        maximum = int32(maximum + modifiers.get(category, 0))
    modifiable = rule["range_modifiable"]
    bonus, carried = 0, False
    if maximum >= 1 and modifiable:
        bonus = (getattr(caster, "characteristics", None) or {}).get("RANGE")
        carried = getattr(caster, "is_carried", None)
    minimum, maximum = effective_range(
        rule["minimum"], maximum, modifiable, bonus, carried, 2 in properties
    )
    return dict(rule, minimum=minimum, maximum=maximum)
