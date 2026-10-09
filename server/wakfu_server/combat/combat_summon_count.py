"""Actual fight branch of eGj.GF over complete fdt IN/OFF_PLAY actors."""
from .combat_native_death_status import native_is_dead


def registered_summon_counts(fight, owner_id, records, ordinary, ordinary_view):
    from .combat_global_pv_collections import _collections
    from .combat_trove_long_map import NativeTroveLongMap

    if not hasattr(fight, "native_global_pv_collections"):
        return None
    state = _collections(fight)
    identities = NativeTroveLongMap(state["fighters"]).order()
    if not set(identities) <= set(fight.actors) or set(fight.actors) - set(
        identities
    ) - set(state["retired_fighters"]):
        raise ValueError("Missing complete actual fdt count population")
    histogram = {}
    for identity in identities:
        status = state["fighter_status"].get(str(identity))
        if status not in ("IN_PLAY", "OFF_PLAY", "OUT_OF_PLAY"):
            raise ValueError("Missing actual count population status")
        if status == "OUT_OF_PLAY":
            continue
        actor = fight.actors[identity]
        record = records.get(identity)
        if record is None:
            metadata = ordinary(ordinary_view, actor)
            if metadata.targeting.get("is_eGj") is not True:
                continue
            if metadata.targeting.get("dTE") is False:
                continue
            return None  # Unregistered summon ownership is not inferred.
        targeting = record["authority"]["targeting"]
        if targeting.get("is_eGj") is not True or targeting.get("dTE") is not True:
            return None
        dead = native_is_dead(actor)
        if dead is None:
            return None
        if dead:
            continue
        controller = getattr(actor, "native_controller_id", None)
        if type(controller) is not int:
            return None
        if (
            type(record.get("controller_id")) is not int
            or controller != record["controller_id"]
        ):
            return None  # A changed relation needs its current registration producer.
        if controller != owner_id or identity == owner_id:
            continue
        properties = getattr(actor, "native_fight_properties", None)
        if properties is None:
            return None
        if 103 in properties:
            continue
        breed = record["authority"]["breed_id"]
        histogram[breed] = histogram.get(breed, 0) + 1
    return sum(histogram.values()), histogram
