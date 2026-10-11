"""Native eLw center: selected eHg.baM, including registered Qq PVs."""
from .combat_native_actor_lookup import native_actor
from .combat_state_managers import registered_area_pv


def team_area_center(fight, invocation, selector):
    target = selector.lower() == "target"
    if target and getattr(invocation, "native_target_cell_argument", False):
        return invocation.cell
    identity = invocation.target_id if target else invocation.caster_id
    if identity is None:
        return invocation.cell if target else None
    selected = native_actor(fight, identity)
    if selected is None:
        selected = registered_area_pv(fight, identity)
    if selected is None:
        raise ValueError("Missing native team-area selected PV")
    return selected.position
