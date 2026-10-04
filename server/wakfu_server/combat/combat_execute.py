"""Transactional execution of the audited adjacent Ouginak6261/6266 branches.

The caller serializes access to a session/fight. Cast6260's mandatory MP theft effects
remain unsupported; this executor cannot silently omit them. Packets and live
actor snapshots are built on a copy before committing any fight state.
"""
from copy import deepcopy
from .combat_cast import prepare_cast
from .combat_bare_effects import bare_damage_selector
from .combat_effects import direct_damage, mp_loss
from .combat_spells import cast_animation, cast_notification
from .combat_actor import actual_actor_stats, actual_monster_actor_stats
from .combat_los import static_visible


def adjacent_native_los(map_id, source, target, fight):
    """Native static LOS for neighboring cells; no intermediate actor blockers."""
    if abs(source[0] - target[0]) + abs(source[1] - target[1]) != 1:
        return False
    return static_visible(map_id, source, target)


def execute_adjacent_cast(
    body,
    character,
    monster,
    fight,
    owner_id,
    deck_blob,
    *,
    wp_current,
    wp_maximum,
    action_id,
    effect_uid,
    critical_chance,
    running_effects,
    summons,
    bonuses,
    mitigate,
    mp_resistance_caster=None,
    mp_resistance_target=None,
    mp_immune=None
):
    selector = bare_damage_selector(
        critical_chance=critical_chance,
        running_effects=running_effects,
        summons=summons,
        bonuses=bonuses,
    )
    preview = deepcopy(fight)
    plan = prepare_cast(
        body,
        character,
        preview,
        owner_id,
        deck_blob,
        wp=wp_current,
        line_of_sight=lambda source, target, state: adjacent_native_los(
            character["map_id"], source, target, state
        ),
        select_effect=selector,
        mitigate=mitigate,
        complete=False,
    )
    if plan["spell_id"] not in (6261, 6266) or plan["costs"]["wp"]:
        raise ValueError("No complete transactional executor for this spell")
    caster = preview.actors[plan["actor_id"]]
    target = preview.actors[plan["target_id"]]
    monster = selected_monster(monster, target.id)
    if target.id != monster["id"] or target.controlled:
        raise ValueError("Damage target is not the owned monster")
    if plan["spell_id"] == 6261 and (
        mp_resistance_caster != 0 or mp_resistance_target != 0 or mp_immune is not False
    ):
        raise ValueError("MP loss requires audited zero resistance and no immunity")
    if plan["spell_id"] == 6261 and plan["damage"] >= target.hp:
        raise ValueError("MP loss after a lethal hit has not been audited")
    preview.spend(owner_id, caster.id, ap=plan["costs"]["ap"], mp=plan["costs"]["mp"])
    previous_events = len(preview.events)
    dealt = preview.apply_damage(caster.id, target.id, plan["damage"])
    packets = [
        (
            12588,
            cast_animation(
                fight.id, action_id, character, plan["spell_id"], plan["target"]
            ),
        ),
        (
            12678,
            cast_notification(
                fight.id, action_id, character, plan["spell_id"], plan["target"]
            ),
        ),
        (
            12613,
            direct_damage(
                fight.id,
                action_id,
                uid=effect_uid,
                generic_effect=plan["generic_effect"],
                element=plan["element"],
                caster_id=caster.id,
                target_id=target.id,
                damage=dealt,
            ),
        ),
    ]
    if plan["spell_id"] == 6261:
        lost = min(target.mp, 1)
        target.mp -= lost
        preview._sync_resources(target)
        packets.append(
            (
                12613,
                mp_loss(
                    fight.id,
                    action_id,
                    uid=effect_uid + 1,
                    caster_id=caster.id,
                    target_id=target.id,
                    amount=lost,
                ),
            )
        )
        preview._event(
            "mp_loss",
            source_id=caster.id,
            target_id=target.id,
            amount=lost,
            mp=target.mp,
        )
    plan.update(complete=True, pending_side_effects=None)
    snapshots = {
        caster.id: actual_actor_stats(
            character, caster, fight.id, wp_current=wp_current, wp_maximum=wp_maximum
        ),
        target.id: actual_monster_actor_stats(
            monster,
            target,
            fight.id,
            wp_current=monster["wp"],
            wp_maximum=monster.get("max_wp", monster["wp"]),
            direction=monster.get("direction", 3),
        ),
    }
    # Keep existing Actor objects live for callers holding references. No
    # operation that can fail follows this commit boundary.
    for actor_id, copy in preview.actors.items():
        fight.actors[actor_id].__dict__.update(copy.__dict__)
    for key, value in preview.__dict__.items():
        if key != "actors":
            setattr(fight, key, value)
    return dict(
        plan=plan,
        damage=dealt,
        packets=packets,
        snapshots=snapshots,
        events=preview.events[previous_events:],
    )


def selected_monster(monsters, target_id):
    """Resolve an owned NPC from a single instance, sequence or ID mapping."""
    if isinstance(monsters, dict) and "id" in monsters:
        records = [monsters]
    elif isinstance(monsters, dict):
        records = list(monsters.values())
    else:
        records = list(monsters)
    ids = [entry["id"] for entry in records]
    if len(ids) != len(set(ids)) or target_id not in ids:
        raise ValueError("Selected target is absent or duplicate in owned NPC roster")
    return next(entry for entry in records if entry["id"] == target_id)
