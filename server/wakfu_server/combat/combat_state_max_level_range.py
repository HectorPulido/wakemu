"""eLt: maximum FIRST retained state level over actual fighter/area PVs."""
from dataclasses import dataclass


@dataclass(frozen=True)
class StateLevelPV:
    position: tuple
    physical_radius: int
    fight_properties: frozenset
    # Native Qf LinkedHashMap.values order, not sorted UID/state-level order.
    carriers: tuple  # (state reference, exact level, original caster Sn).


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _axis_distance(value, center, radius):
    delta = _i32(value - center)
    magnitude = delta if delta == -(1 << 31) else abs(delta)
    return max(0, _i32(magnitude - radius))


def maximum_state_level(
    rows,
    *,
    center,
    minimum,
    maximum,
    reference,
    owner_id=None,
    native_caster_present=True
):
    if center is None:
        return 0  # eLt returns before enumerating the state-bearing population.
    if any(
        type(v) is not int or not -(1 << 63) <= v < (1 << 63)
        for v in (minimum, maximum, reference)
    ):
        raise ValueError("Missing native eLt long operands")
    if (
        not isinstance(center, (tuple, list))
        or len(center) != 3
        or any(type(v) is not int for v in center)
    ):
        raise ValueError("Missing native eLt center aBn")
    if owner_id is not None and (
        type(owner_id) is not int or not -(1 << 63) <= owner_id < (1 << 63)
    ):
        raise ValueError("Missing native eLt optional caster identity")
    if type(native_caster_present) is not bool:
        raise ValueError("Missing native eLt source eHg nullability")
    if owner_id is not None and not native_caster_present:
        return -1  # eLt.a rejects every carrier when its root eHg is null.
    result = -1
    for row in rows:
        if (
            not isinstance(row, StateLevelPV)
            or type(row.physical_radius) is not int
            or not -128 <= row.physical_radius <= 127
            or not isinstance(row.fight_properties, frozenset)
            or any(type(v) is not int for v in row.fight_properties)
            or not isinstance(row.position, tuple)
            or len(row.position) != 3
            or any(type(v) is not int for v in row.position)
        ):
            raise ValueError("Missing actual native eLt PV snapshot")
        matching = []
        for carrier in row.carriers:
            if (
                not isinstance(carrier, tuple)
                or len(carrier) != 3
                or any(type(v) is not int for v in carrier)
            ):
                raise ValueError("Missing actual native eZk carrier")
            if carrier[0] == reference:
                matching.append(carrier)
        if not matching:
            continue
        if owner_id is not None and not any(
            carrier[2] == owner_id for carrier in matching
        ):
            continue
        if 42 in row.fight_properties:  # ffe.sem, independent of state source.
            continue
        distance = _i32(
            _axis_distance(row.position[0], center[0], row.physical_radius)
            + _axis_distance(row.position[1], center[1], row.physical_radius)
        )
        if maximum >= 0 and not minimum <= distance <= maximum:
            continue
        # The carrier satisfying owner filtering need not be the FIRST carrier
        # returned by PV.df(reference). Native eLt does these as separate steps.
        result = max(result, matching[0][1])
    return result


def ordered_registered_state_carriers(fight, manager):
    from .combat_retained_runtime import native_retained_condition_effects

    by_uid = {entry.uid: entry for entry in manager.state_ledger.entries}
    if len(by_uid) != len(manager.state_ledger.entries):
        raise ValueError("Duplicate actual native state carrier UID")
    result = []
    for _, family, uid in native_retained_condition_effects(fight, manager.id):
        if family != 310:
            continue
        entry = by_uid.get(uid)
        if entry is None:
            raise ValueError("Missing actual registered eZk state carrier")
        result.append((entry.reference, entry.level, entry.caster_id))
    return tuple(result)


def state_level_population(fight, actor_authority):
    """Actual fbX.fUQ(IN_PLAY) plus Qs managers, with tracked native Qf order."""
    from .combat_native_actor_lookup import native_actor_population
    from .combat_global_pv_collections import global_fighter_guards, global_area_order
    from .combat_range_conditions import attest_state_area_population
    from .combat_effect_area_queries import _rows
    from .combat_state_managers import state_manager, registered_area_pv

    if not hasattr(fight, "native_global_pv_collections"):
        raise ValueError("Missing complete native eLt fdt/Qs population")
    result = []
    for actor in native_actor_population(fight):
        if not global_fighter_guards(fight, actor.id)["baF"]:
            continue
        from .combat_runtime_adapter import NativeActorAuthority

        metadata = actor_authority(fight, actor)
        if (
            not isinstance(metadata, NativeActorAuthority)
            or metadata.targeting.get("is_eGj") is not True
        ):
            raise ValueError("Missing actual native eLt fighter authority")
        carriers = ordered_registered_state_carriers(fight, actor)
        if carriers:
            result.append(
                StateLevelPV(
                    tuple(actor.position),
                    actor.physical_radius,
                    actor_authority.properties(fight, actor),
                    carriers,
                )
            )
    global_area_order(fight)
    # Retain the existing complete null-Qf/known-empty/Qf attestation rather
    # than treating an absent ledger as an invented empty native manager.
    attest_state_area_population(fight)
    for row in _rows(fight):
        if (
            "state_ledger" not in row
            or row.get("native_running_effect_manager") is False
        ):
            continue
        manager = state_manager(fight, row["uid"])
        if manager is None:
            continue
        carriers = ordered_registered_state_carriers(fight, manager)
        if not carriers:
            continue
        pv = registered_area_pv(fight, row["uid"])
        if pv is None:
            raise ValueError("Missing actual eLt area PV")
        result.append(
            StateLevelPV(tuple(pv.position), 0, pv.native_fight_properties, carriers)
        )
    return tuple(result)
