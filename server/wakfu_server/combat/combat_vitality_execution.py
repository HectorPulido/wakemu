"""Shared native vitality consumption and mutation boundaries.

Handlers retain native selection, runner phases and delivery preparation. These
components consume live snapshots after L2 and apply only the corresponding
characteristic changes; HP/death authority stays with Fight.
"""
from .combat_damage_healing import (
    consume_damage,
    consume_healing,
    healing_resistance_after,
)


def plan_damage_consumption(
    amount,
    source,
    source_stats,
    target,
    target_stats,
    wall,
    target_hp,
    context,
    interpreted,
):
    result = consume_damage(
        amount,
        source_barrier=source_stats[100],
        target_armor=target_stats.get(97, 0),
        target_virtual_hp=target_stats.get(92, 0),
        target_hp=target_hp,
        blocked=context.blocked,
        bypass_armor_and_barrier=interpreted["bypass_armor_and_barrier"],
        frozen_stats=tuple(("source", k) for k in source.effect_frozen)
        + (
            ()
            if wall is not None
            else tuple(("target", k) for k in target.effect_frozen)
        ),
    )
    return result


def plan_healing_consumption(amount, target, target_stats, context):
    result = consume_healing(
        amount,
        target_hp=target.hp,
        target_max_hp=target.max_hp,
        target_virtual_hp=target_stats[92],
        target_max_virtual_hp=target.effect_maxima[92],
        undead=context.undead,
        bypass_undead=context.bypass_undead,
        frozen_stats=tuple(("target", k) for k in target.effect_frozen),
    )
    from .combat_hp_raw import hp_raw_present, hp_shift_result

    if hp_raw_present(target):
        from .combat_casting_range import int32

        _, hp_after, hp_actual = hp_shift_result(target, amount)
        remainder = int32(amount - hp_actual)
        virtual_requested = None
        if target.effect_maxima[92] <= 0:
            virtual_after, virtual_actual = target_stats[92], 0
        elif getattr(target, "native_copy_pa_source", None) is not None:
            from .combat_copied_pa import copied_shift_result

            _, virtual_after, virtual_actual = copied_shift_result(
                target, 92, remainder
            )
            virtual_requested = remainder
        else:
            virtual_actual = (
                0
                if 92 in target.effect_frozen
                else min(remainder, target.effect_maxima[92] - target_stats[92])
            )
            virtual_after = target_stats[92] + virtual_actual
        result.update(
            value=int32(hp_actual + virtual_actual),
            hp_gain=hp_actual,
            hp_requested=amount,
            virtual_hp_gain=virtual_actual,
            virtual_hp_requested=virtual_requested,
            target_hp=hp_after,
            target_virtual_hp=virtual_after,
        )
    result["target_heal_resistance"] = healing_resistance_after(
        result["value"],
        target_max_hp=target.max_hp,
        current=target_stats[32],
        enabled=context.resistance_enabled,
        frozen=32 in target.effect_frozen,
        minimum=context.resistance_minimum,
        maximum=context.resistance_maximum,
    )
    return result


def apply_area_damage(fight, source_id, wall, amount):
    """Mutate native Qq HP without retiring its active spatial identity."""
    if type(amount) is not int or amount < 0 or source_id not in fight.actors:
        raise ValueError("Invalid native fbd damage application")
    row, constructor = wall["row"], wall["constructor"]
    from .combat_wall_area import update_wall_hp

    current = wall["snapshot"]["current_hp"]
    dealt = min(current, amount)
    after = current - dealt
    if not callable(getattr(fight, "_event", None)):
        raise ValueError("Missing native fbd damage event ledger")
    if row["native_area_contract"] == "faW":
        from .combat_fake_fighter_resources import update_fake_fighter_hp

        update_fake_fighter_hp(row, wall["definition"], after)
    else:
        update_wall_hp(row, constructor, after)
    fight._event(
        "damage", source_id=source_id, target_id=row["uid"], amount=dealt, hp=after
    )
    return dealt


def apply_damage_consumption(
    fight,
    source,
    target,
    wall,
    result,
    source_stats,
    target_stats,
    effect,
    invocation,
    uid,
    event_lifecycle,
):
    """Apply HP/death, then source barrier, then target absorption in native order."""
    if wall is not None:
        apply_area_damage(fight, source.id, wall, result["hp_loss"])
    else:
        from .combat_hp_raw import hp_raw_present

        death = getattr(event_lifecycle, "death", None)
        fight.apply_effect_damage(
            source.id,
            target.id,
            result["hp_requested"] if hp_raw_present(target) else result["hp_loss"],
            native_runner_effect=effect,
            native_death_delivery=(
                None
                if not callable(death)
                else lambda actor_id: event_lifecycle.death(
                    actor_id,
                    effect=effect,
                    invocation=invocation,
                    uid=uid,
                    value=result["value"],
                )
            ),
        )
    if getattr(source, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import set_copied_current

        set_copied_current(fight, source, 100, result["source_barrier"])
    source_stats[100] = result["source_barrier"]
    if wall is None:
        writes = ((97, "target_armor"), (92, "target_virtual_hp"))
        if getattr(target, "native_copy_pa_source", None) is not None:
            from .combat_copied_pa import set_copied_current

            for stat, key in writes:
                set_copied_current(fight, target, stat, result[key])
        for stat, key in writes:
            target_stats[stat] = result[key]


def apply_healing_consumption(fight, source, target, result, target_stats):
    """Apply HP first and preserve copied raw-current PA setter semantics."""
    fight.apply_effect_healing(
        source.id, target.id, result.get("hp_requested", result["hp_gain"])
    )
    if getattr(target, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import shift_copied_current, set_copied_current

        if result["virtual_hp_requested"] is not None:
            shift_copied_current(fight, target, 92, result["virtual_hp_requested"])
        set_copied_current(fight, target, 32, result["target_heal_resistance"])
    for stat, key in ((92, "target_virtual_hp"), (32, "target_heal_resistance")):
        target_stats[stat] = result[key]
