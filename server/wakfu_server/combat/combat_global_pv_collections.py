"""Fresh fdt/Qs/fbX PV collection topology captured at actual registration.

These explicit producer APIs never reconstruct native maps from a restored
roster. Missing legacy topology remains unknown. State contains plain values.
"""
from .combat_trove_long_map import NativeTroveLongMap
from .combat_global_event_iterator import native_global_event_iterator

SOURCE = "fresh.fdt_saq.Qs_bhs.fbX_rRc.default_Trove"


def initialize_global_pv_collections(fight, participant_order):
    if hasattr(fight, "native_global_pv_collections"):
        raise ValueError("Native global PV collections already initialized")
    if (
        not isinstance(participant_order, tuple)
        or len(participant_order) != len(set(participant_order))
        or set(participant_order) != set(fight.actors)
        or getattr(fight, "native_effect_areas", {})
    ):
        raise ValueError("Exact fresh native participant registration order required")
    fighters, areas, extras = (NativeTroveLongMap() for _ in range(3))
    for identity in participant_order:
        fighters.put(identity)
    fight.native_global_pv_collections = dict(
        source=SOURCE,
        mode="rRm",
        fighters=fighters.state,
        areas=areas.state,
        extras=extras.state,
        retired_fighters=[],
        fighter_status={str(identity): "IN_PLAY" for identity in participant_order},
    )


def _collections(fight):
    state = getattr(fight, "native_global_pv_collections", None)
    if (
        not isinstance(state, dict)
        or state.get("source") != SOURCE
        or set(state)
        != {
            "source",
            "mode",
            "fighters",
            "areas",
            "extras",
            "fighter_status",
            "retired_fighters",
        }
        or state.get("mode") not in ("rRm", "rRn", "rRo")
    ):
        raise ValueError("Missing actual native global PV collection producer")
    return state


def set_global_pv_mode(fight, mode):
    if mode not in ("rRm", "rRn", "rRo"):
        raise ValueError("Actual native fbZ mode required")
    _collections(fight)["mode"] = mode


def register_global_fighter(fight, identity):
    state = _collections(fight)
    if identity not in fight.actors:
        raise ValueError("Actual newly registered fighter required")
    if not NativeTroveLongMap(state["fighters"]).put(identity):
        raise ValueError("Duplicate native fighter collection registration")
    if identity in state["retired_fighters"]:
        state["retired_fighters"].remove(identity)
    state["fighter_status"][str(identity)] = "IN_PLAY"  # Actual fdy constructor.


def set_global_fighter_status(fight, identity, status):
    state = _collections(fight)
    if status not in ("IN_PLAY", "OFF_PLAY", "OUT_OF_PLAY") or not NativeTroveLongMap(
        state["fighters"]
    ).contains(identity):
        raise ValueError("Actual native fighter registry transition required")
    state["fighter_status"][str(identity)] = status


def global_fighter_guards(fight, identity):
    """eGj.baF/baG/baK project actual fdy status, independently of HP."""
    state = _collections(fight)
    if not NativeTroveLongMap(state["fighters"]).contains(identity):
        raise ValueError("Actual native fdy registration required")
    status = state["fighter_status"].get(str(identity))
    if status not in ("IN_PLAY", "OFF_PLAY", "OUT_OF_PLAY"):
        raise ValueError("Missing actual native fighter status")
    return dict(
        baF=status == "IN_PLAY", baG=status == "OFF_PLAY", baK=status == "OUT_OF_PLAY"
    )


def global_fighter_registered(fight, identity):
    """Actual fdt membership, independent of fdy IN/OFF/OUT_PLAY status.

    Owned registration follows eGj.a(fcb), which writes pGz=true; native
    withdrawal removes that registration. This is not an HP/baF projection.
    """
    state = _collections(fight)
    registered = NativeTroveLongMap(state["fighters"]).contains(identity)
    if registered:
        if identity in state["retired_fighters"]:
            raise ValueError("Native fighter is both registered and retired")
        global_fighter_guards(fight, identity)
        return True
    if (
        identity in state["retired_fighters"]
        and str(identity) not in state["fighter_status"]
    ):
        return False
    raise ValueError("Missing actual native fighter registration authority")


def global_fighter_participates(fight, identity):
    """Use actual fdy IN_PLAY or attested fdt removal, never current HP."""
    state = _collections(fight)
    registered = NativeTroveLongMap(state["fighters"]).contains(identity)
    retired = identity in state["retired_fighters"]
    if not registered:
        if retired and str(identity) not in state["fighter_status"]:
            return False
        raise ValueError("Missing actual native fighter participation authority")
    if retired:
        raise ValueError("Native fighter is both registered and retired")
    return global_fighter_guards(fight, identity)["baF"]


def unregister_global_fighter(fight, identity):
    """Actual fdt.bx removal, distinct from OFF_PLAY or OUT_OF_PLAY status."""
    state = _collections(fight)
    if not NativeTroveLongMap(state["fighters"]).remove(identity):
        raise ValueError("Actual fdt fighter removal required")
    state["fighter_status"].pop(str(identity))
    state["retired_fighters"].append(identity)


def register_global_area(fight, identity):
    state = _collections(fight)
    if identity not in getattr(fight, "native_effect_areas", {}):
        raise ValueError("Actual Qs area registration required")
    if not NativeTroveLongMap(state["areas"]).put(identity):
        raise ValueError("Duplicate native Qs collection registration")


def global_area_order(fight):
    """Actual Qs.bhs iteration, independent of fighter/global event filtering."""
    order = NativeTroveLongMap(_collections(fight)["areas"]).order()
    if set(order) != set(getattr(fight, "native_effect_areas", {})):
        raise ValueError("Native Qs area collection disagrees with registration")
    return order


def unregister_global_area(fight, identity):
    if not NativeTroveLongMap(_collections(fight)["areas"]).remove(identity):
        raise ValueError("Actual Qs area removal required")


def global_pv_iterator(fight, *, caster_id, caster_only=None):
    state = _collections(fight)
    if caster_only is None:
        caster_only = state["mode"] == "rRo" and caster_id is not None
    fighters = NativeTroveLongMap(state["fighters"])
    areas = NativeTroveLongMap(state["areas"])
    extras = NativeTroveLongMap(state["extras"])
    fighter_ids = set(fighters.order())
    if (
        not fighter_ids <= set(fight.actors)
        or set(fight.actors) - fighter_ids - set(state["retired_fighters"])
        or set(areas.order()) != set(getattr(fight, "native_effect_areas", {}))
    ):
        raise ValueError("Native PV collection changed without registration producer")

    def eligible(identity):
        # fcd.v reads status and collection membership at each next().
        if fighters.contains(identity):
            status = state["fighter_status"].get(str(identity))
            if status not in ("IN_PLAY", "OFF_PLAY", "OUT_OF_PLAY"):
                raise ValueError("Missing actual native fighter status")
            if status in ("IN_PLAY", "OFF_PLAY"):
                return True
        return areas.contains(identity) or extras.contains(identity)

    # fcb.dLy creates a filtered ArrayList before global delivery; changes
    # during reactions affect fcd.v, not that already captured candidate list.
    fighter_order = tuple(
        identity
        for identity in fighters.order()
        if state["fighter_status"].get(str(identity)) in ("IN_PLAY", "OFF_PLAY")
    )
    return native_global_event_iterator(
        fighter_order=fighter_order,
        area_order=areas.order(),
        extra_order=extras.order(),
        eligible=eligible,
        caster_only=caster_only,
        caster_id=caster_id,
    )
