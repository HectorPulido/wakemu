"""Audited adjacent Iop4785 and armor-free Iop4780 damage/state branches.

Only state3442 (native additive marker, NullEffect400) may already exist.
State3444's combo/MP changes, target3467 and cost state6117 are unsupported.
Adjacency makes passive8420's distance3 branch false. Crit remains explicit0.
"""
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT
import json
from pathlib import Path
from copy import deepcopy
from .combat_cast import decode_cast
from .combat_execute import selected_monster, adjacent_native_los
from .combat_actor import actual_actor_stats, actual_monster_actor_stats
from .combat_effects import direct_damage
from .combat_spells import cast_animation, cast_notification
from .combat_states import state_packet, plan_3425, plan_8913
from wakfu_server.spells import validate_deck
from wakfu_server.spell_audit import catalog as effect_catalog
from .combat_parameters import parameter_value

_RULES = {
    id: protocol_catalog.load(DATA_ROOT / f"iop{id}-combat.json") for id in (4785, 4780)
}


def execute_iop_cast(
    body,
    character,
    monsters,
    fight,
    owner_id,
    deck_blob,
    *,
    wp_current,
    wp_maximum,
    action_id,
    effect_uid,
    critical_chance,
    caster_states,
    target_states,
    caster_bonuses,
    target_bonuses,
    other_running_effects,
    mitigate,
    target_armor=None,
    state_expiry_enabled=False,
):
    request = decode_cast(body)
    spell_id = request["spell_uid"] & 0xFFFFFFFF
    if spell_id not in _RULES:
        raise ValueError("No audited Iop executor for this spell")
    rule = _RULES[spell_id]
    pc = fight._current_owned(owner_id, request["actor_id"])
    if (
        pc.id != character["id"]
        or character["breed"] != 8
        or request["spell_uid"] != ((pc.id << 32) | spell_id)
    ):
        raise ValueError("Cast is not the owned Iop4785 spell")
    deck = validate_deck(deck_blob, 8, pc.effective_level)
    if spell_id not in deck["active"]:
        raise ValueError("Iop4785 absent from current deck")
    if (
        critical_chance != 0
        or other_running_effects is None
        or tuple(other_running_effects)
        or target_states is None
        or (dict(target_states) and spell_id == 4785)
        or set(target_states or {}) - {8913}
        or caster_bonuses is None
        or any(caster_bonuses.values())
        or target_bonuses is None
        or any(target_bonuses.values())
    ):
        raise ValueError("Unsupported Iop target states, critical or bonuses")
    states = plan_3425(caster_states, rule["state_level"])
    if spell_id == 4780 and state_expiry_enabled is not True:
        raise ValueError("Iop4780 requires native caster-start8913 expiry hook")
    target_state = (
        plan_8913(caster_id=pc.id, caster_turn=pc.turn_count, target_armor=target_armor)
        if spell_id == 4780
        else None
    )
    if hasattr(pc, "combat_states") and pc.combat_states != caster_states:
        raise ValueError("Stale authoritative caster state collection")
    cell = request["target"]
    npc = next(
        (a for a in fight.actors.values() if a.hp > 0 and a.position == cell), None
    )
    if npc is None or npc.controlled or npc.team == pc.team:
        raise ValueError("Target is not a living enemy NPC")
    monster = selected_monster(monsters, npc.id)
    if hasattr(npc, "combat_states") and npc.combat_states != target_states:
        raise ValueError("Stale authoritative target state collection")
    if cell not in fight.walkable or not adjacent_native_los(
        character["map_id"], pc.position, cell, fight
    ):
        raise ValueError("Iop4785 outside native adjacent range/LOS")
    if pc.ap < rule["ap"]:
        raise ValueError("Insufficient AP")
    damage_effect = effect_catalog()["effects"][str(rule["generic_effect"])]
    damage = mitigate(
        parameter_value(damage_effect["parameters"], 0, pc.effective_level),
        rule["element"],
        pc,
        npc,
        fight,
    )
    if type(damage) is not int or not 0 <= damage < (1 << 31):
        raise ValueError("Invalid authoritative damage")
    if spell_id == 4780 and damage >= npc.hp:
        raise ValueError("8913 application after a lethal hit has not been audited")
    preview = deepcopy(fight)
    pc = preview.actors[pc.id]
    npc = preview.actors[npc.id]
    previous = len(preview.events)
    preview.spend(owner_id, pc.id, ap=rule["ap"])
    dealt = preview.apply_damage(pc.id, npc.id, damage)
    packets = [
        (
            12588,
            cast_animation(
                fight.id,
                action_id,
                dict(character, level=pc.effective_level),
                spell_id,
                cell,
            ),
        ),
        (
            12678,
            cast_notification(
                fight.id,
                action_id,
                dict(character, level=pc.effective_level),
                spell_id,
                cell,
            ),
        ),
        (
            12613,
            direct_damage(
                fight.id,
                action_id,
                uid=effect_uid,
                generic_effect=rule["generic_effect"],
                element=rule["element"],
                caster_id=pc.id,
                target_id=npc.id,
                damage=dealt,
            ),
        ),
        (
            12613,
            state_packet(
                fight.id,
                action_id,
                uid=effect_uid + 1,
                generic_effect=rule["state_generic"],
                caster_id=pc.id,
                target_id=pc.id,
                state_id=3425,
                level=rule["state_level"],
            ),
        ),
    ]
    if target_state is not None:
        packets.insert(
            3,
            (
                12613,
                state_packet(
                    fight.id,
                    action_id,
                    uid=effect_uid + 2,
                    generic_effect=290752,
                    caster_id=pc.id,
                    target_id=npc.id,
                    state_id=8913,
                    level=30,
                ),
            ),
        )
        npc.combat_states = {8913: target_state}
    pc.combat_states = states
    snapshots = {
        pc.id: actual_actor_stats(
            character, pc, fight.id, wp_current=wp_current, wp_maximum=wp_maximum
        ),
        npc.id: actual_monster_actor_stats(
            monster,
            npc,
            fight.id,
            wp_current=monster["wp"],
            wp_maximum=monster.get("max_wp", monster["wp"]),
            direction=monster.get("direction", 3),
        ),
    }
    preview._event(
        "cast", actor_id=pc.id, target_id=npc.id, spell_id=spell_id, ap_cost=rule["ap"]
    )
    preview._event(
        "state",
        actor_id=pc.id,
        state_id=3442,
        level=states[3442],
        source_state=3425,
        instantaneous=True,
    )
    from .combat_pointer_qi_commit import prepare_pointer_commit

    pointer_binding = prepare_pointer_commit(preview)
    if pointer_binding is not None:
        pointer_binding.stage(fight)
    for identity, copy in preview.actors.items():
        fight.actors[identity].__dict__.update(copy.__dict__)
    for key, value in preview.__dict__.items():
        if key != "actors":
            setattr(fight, key, value)
    if pointer_binding is not None:
        pointer_binding.publish()
    return dict(
        damage=dealt,
        packets=packets,
        snapshots=snapshots,
        states=states,
        events=preview.events[previous:],
    )


def execute_iop4785(*args, **kwargs):
    """Compatibility API for the existing adjacent Iop4785 branch."""
    if decode_cast(args[0])["spell_uid"] & 0xFFFFFFFF != 4785:
        raise ValueError("Expected Iop4785 request")
    return execute_iop_cast(*args, **kwargs)
