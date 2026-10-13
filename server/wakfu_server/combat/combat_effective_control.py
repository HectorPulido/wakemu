"""Current native control routing without changing original actor identity."""
from .combat_controller_registry import current_native_controller


def effective_server_controlled(fight, actor):
    """Registered eGj.fqL routes AI; legacy snapshots retain original behavior."""
    if not hasattr(fight, "native_controller_registry"):
        return not actor.controlled
    if fight.actors.get(actor.id) is not actor:
        raise ValueError("Missing registered control actor")
    current_native_controller(fight, actor.id)
    value = getattr(actor, "native_controlled_by_ai", None)
    if type(value) is not bool:
        raise ValueError("Missing actual native eGj.fqL control flag")
    if value:
        return True
    from .combat_npc_controller_policy import npc_controller_routes_ai

    return npc_controller_routes_ai(fight, actor)


def effective_input_owner(fight, actor):
    """Resolve actual current fdy controller; original ownership stays immutable."""
    if effective_server_controlled(fight, actor):
        return None
    if not hasattr(fight, "native_controller_registry"):
        return actor.owner_id if actor.controlled else None
    controller = current_native_controller(fight, actor.id)
    if controller is None:
        return None
    source = fight.actors.get(controller)
    if source is None or not source.controlled:
        return None
    return source.owner_id


def require_effective_owner(fight, actor, owner_id):
    actual = effective_input_owner(fight, actor)
    if actual is None or actual != owner_id:
        raise ValueError("Actor is not controlled by this owner")
    return actor


def effective_affiliation(fight, actor):
    """Current native team for decisions, preserving the actor's original team."""
    if hasattr(fight, "native_controller_registry"):
        from .combat_controller_registry import current_native_team

        return current_native_team(fight, actor.id)
    value = getattr(actor, "native_fight_affiliation", actor.team)
    if type(value) is not int or not -128 <= value < 128:
        raise ValueError("Missing actual native fight affiliation")
    return value
