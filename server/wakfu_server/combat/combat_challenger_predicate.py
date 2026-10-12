"""Native eNC/eII actor kind check for PLAYER_CHARACTER or COMPANION."""


def native_challenger(context, selector):
    """Read the actual selected eHg; explicit native null returns false."""
    from .combat_conditions import UnknownCondition

    actor = context.actors.get(selector)
    if actor is None:
        if selector in context.null_actor_aliases or (
            selector in ("triggeringcaster", "triggeringtarget")
            and context.triggering_effect_present is False
        ):
            return False
        raise UnknownCondition("Missing native challenger actor authority")
    if actor.is_native_ehg is False:
        return False  # eII.a returns null when selected PV is not an eHg.
    if type(actor.is_challenger) is not bool:
        raise UnknownCondition("Missing native PLAYER_CHARACTER/COMPANION kind")
    return actor.is_challenger
