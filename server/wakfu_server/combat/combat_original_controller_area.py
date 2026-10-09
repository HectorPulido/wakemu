"""eYS1008.bch: source caster eGj.dpr, other PV unchanged."""
from .combat_native_actor_lookup import native_actor
from .combat_state_managers import registered_area_pv


def original_controller_area_creator(fight, source_id, authority):
    if source_id is None:
        return None  # Original eYS preserves null bfr; fbm creator ID0.
    if type(source_id) is not int or not -(1 << 63) <= source_id < (1 << 63):
        raise ValueError("Unknown native eYS source PV identity")
    actor = native_actor(fight, source_id)
    if actor is None:
        if registered_area_pv(fight, source_id) is None:
            raise ValueError("Unknown native eYS nonfighter PV")
        return source_id  # eYS instanceof eGj branch is false.
    if not callable(authority):
        raise ValueError("Missing native eYS source type/controller authority")
    targeting = authority(fight, actor).targeting
    if type(targeting.get("is_eGj")) is not bool:
        raise ValueError("Unknown native eYS instanceof eGj")
    if targeting["is_eGj"] is False:
        return source_id
    controller = targeting.get("dpr_id")
    if (
        type(controller) is not int
        or not -(1 << 63) <= controller < (1 << 63)
        or controller == 0
    ):
        raise ValueError("Missing native eYS original controller dpr")
    if native_actor(fight, controller) is None:
        raise ValueError("Unowned native eYS original controller PV")
    return controller
