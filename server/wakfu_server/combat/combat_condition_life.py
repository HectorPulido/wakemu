"""Native eNJ/eOe life conditions; dsA, baF and baG are separate facts."""


def life_predicate(context, name, selector):
    from .combat_conditions import UnknownCondition

    if callable(context.life_actor_query):
        try:
            value = context.life_actor_query(name, selector)
        except ValueError as error:
            raise UnknownCondition(str(error)) from error
        if type(value) is not bool:
            raise UnknownCondition("Missing typed native life condition result")
        return value
    if (
        selector == "target"
        and context.target_cell_is_explicit
        and context.native_cell_target_fighter_resolved is not True
    ):
        raise UnknownCondition("Missing native QI first fighter life selection")
    actor = context.actors.get(selector)
    if actor is None:
        if selector in context.null_actor_aliases:
            return False
        raise UnknownCondition("Missing native life condition actor")
    if name == "IsDead":
        kind, value = actor.is_native_fighter, actor.is_dead
    elif name == "IsInPlay":
        kind = True if actor.is_native_fighter is True else actor.is_native_ehg
        value = actor.is_in_play
    else:
        raise UnknownCondition("Unknown native life condition")
    if kind is False:
        return False
    if kind is not True or type(value) is not bool:
        raise UnknownCondition("Missing actual native life type/value authority")
    return value


def registered_life_predicate(fight, actor_authority, name, identity):
    """Direct eGj or registered faV; no HP/owner/roster substitutions."""
    if identity is None:
        return False
    from .combat_native_actor_lookup import native_actor

    actor = native_actor(fight, identity)
    if actor is not None:
        authority = actor_authority(fight, actor)
        kind = authority.targeting.get("is_eGj")
        if kind is False:
            return False
        if kind is not True:
            raise ValueError("Missing native life eGj type")
        value = (
            authority.targeting.get("baF")
            if name == "IsInPlay"
            else getattr(actor, "native_is_dead", None)
        )
        if name == "IsDead" and value is None:
            from .combat_native_death_status import native_is_dead

            value = native_is_dead(actor)
        if type(value) is not bool:
            raise ValueError("Missing actual native baF/dsA authority")
        return value
    from .combat_state_managers import registered_area_pv
    from .combat_area_authority import area_guards

    area = registered_area_pv(fight, identity)
    if area is None:
        raise ValueError("Unregistered native life recipient")
    if name == "IsDead":
        return False  # faV is eHg, but not the eGj required by eNJ.
    return area_guards(fight, identity)["baF"]
