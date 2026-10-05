"""Pure cast validation; terrain LOS and effect conditions remain authoritative.

Common request validation uses native definitions for all class spells and
accepts self and empty-cell targets. Damage execution remains a separate layer
with a limited audited set. No state changes occur during validation; unknown
conditional costs are rejected rather than treated as unconditional.
"""
from .paths import DATA_ROOT
import json
import struct
from pathlib import Path
from .combat_spells import base_costs
from .spells import validate_deck
from .combat_parameters import parameter_value
from .spell_audit import catalog as effect_catalog

_RULES = json.loads((DATA_ROOT / "combat-spell-rules.json").read_text())["spells"]


def decode_cast(body):
    """13260/cpm payload, exactly actorUID, spellUID, x/y/z (26 bytes)."""
    if len(body) != 26:
        raise ValueError("Invalid cpm payload length")
    actor_id, spell_uid, x, y, z = struct.unpack(">qqiih", body)
    return dict(actor_id=actor_id, spell_uid=spell_uid, target=(x, y, z))


def normal_damage_profile(spell_id, level):
    """Native normal branch values; caller must verify its effect conditions."""
    if str(spell_id) not in _RULES or not 1 <= level <= 200:
        raise ValueError("No audited spell damage profile")
    rule = _RULES[str(spell_id)]
    minimum, maximum, _ = rule["levels"][level - 1]
    effect = effect_catalog()["effects"][str(rule["generic_effect"])]
    damage = parameter_value(effect["parameters"], 0, level)
    return dict(rule, minimum=minimum, maximum=maximum, damage=damage)


def prepare_spell_cast(
    body,
    character,
    fight,
    owner_id,
    deck_blob,
    *,
    wp,
    line_of_sight,
    conditional_context=None,
):
    """Validate ownership, deck, resources, native range and terrain only.

    Returning a plan does not execute or validate the effect tree. In
    particular it does not assert that the selected actor can receive effects.
    """
    request = decode_cast(body)
    actor_id = request["actor_id"]
    actor = fight.actors.get(actor_id)
    if (
        fight.phase != "active"
        or fight.current is not actor
        or actor is None
        or not actor.controlled
        or actor.owner_id != owner_id
        or actor_id != character["id"]
        or actor.hp <= 0
    ):
        raise ValueError("Caster is not the owned active actor")
    uid = request["spell_uid"]
    spell_id = uid & 0xFFFFFFFF
    from .combat_spell_grant import granted_spells

    temporary = granted_spells(fight, actor_id).get(spell_id)
    granted = uid == spell_id and temporary is not None and temporary["uid"] == uid
    if not granted:
        if uid != (actor_id << 32) | spell_id:
            raise ValueError("Spell UID belongs to another actor or expired grant")
        deck = validate_deck(deck_blob, character["breed"], character["level"])
        if spell_id not in deck["active"]:
            raise ValueError("Spell is absent from current deck")
    evaluation_level = temporary["level"] if granted else actor.effective_level
    if granted:
        from .combat_native_spell_casting import enabled

        if not enabled():
            raise ValueError("Native temporary spell casting is not enabled")
        from .combat_conditional_costs import ConditionalCostContext
        from .combat_native_spell_casting import definition as native_definition

        context = (
            conditional_context(request, fight)
            if callable(conditional_context)
            else None
        )
        snapshot = getattr(actor, "spell_ap_cost_modifiers", None)
        if isinstance(context, ConditionalCostContext):
            context, snapshot = context.conditions, context.ap_modifiers_by_category
        rule = native_definition(spell_id, evaluation_level, context, snapshot)
        costs, roots = rule["costs"], rule["roots"]
        return _validate_target(
            request,
            actor,
            fight,
            wp,
            costs,
            rule,
            roots,
            evaluation_level,
            line_of_sight,
            spell_id,
            context,
        )
    effective = dict(character, level=actor.effective_level)
    costs = base_costs(effective, spell_id)
    from .combat_conditional_costs import (
        ConditionalCostContext,
        resolve_costs,
        native_modifiers,
        native_catalog,
    )

    if str(spell_id) not in native_catalog()["spell_categories"]:
        raise ValueError("Missing native spell category metadata")
    context = None
    snapshot = getattr(actor, "spell_ap_cost_modifiers", None)
    if callable(conditional_context):
        supplied = conditional_context(request, fight)
        if isinstance(supplied, ConditionalCostContext):
            context, snapshot = supplied.conditions, supplied.ap_modifiers_by_category
        else:
            context = supplied
    if costs["conditional_rules"]:
        if not callable(conditional_context):
            raise ValueError("Conditional spell costs require authoritative context")
        costs = resolve_costs(
            spell_id,
            actor.effective_level,
            costs,
            context,
            modifiers=native_modifiers(spell_id, snapshot),
        )
    elif callable(conditional_context) or hasattr(actor, "spell_ap_cost_modifiers"):
        adjustments = native_modifiers(spell_id, snapshot)
        costs = dict(
            costs,
            **{
                key: max(0, costs[key] + adjustments[key]) for key in ("ap", "mp", "wp")
            },
        )
    # Compatibility for old pure validation fixtures without Actor snapshots:
    # they retain their preexisting unmodified-cost contract. Real Actor has
    # the field and must supply a complete native snapshot (None rejects).
    if actor.ap < costs["ap"] or actor.mp < costs["mp"] or wp < costs["wp"]:
        raise ValueError("Insufficient authoritative spell resources")
    definition = effect_catalog()["spells"].get(str(spell_id))
    if definition is None or not 1 <= actor.effective_level <= 200:
        raise ValueError("Missing native spell definition or unsupported level")
    minimum, maximum, roots = definition["levels"][actor.effective_level - 1]
    rule = dict(definition, minimum=minimum, maximum=maximum)
    return _validate_target(
        request,
        actor,
        fight,
        wp,
        costs,
        rule,
        roots,
        evaluation_level,
        line_of_sight,
        spell_id,
        context,
    )


def _validate_target(
    request,
    actor,
    fight,
    wp,
    costs,
    rule,
    roots,
    evaluation_level,
    line_of_sight,
    spell_id,
    context=None,
):
    if actor.ap < costs["ap"] or actor.mp < costs["mp"] or wp < costs["wp"]:
        raise ValueError("Insufficient authoritative spell resources")
    target_cell = request["target"]
    if target_cell not in fight.walkable:
        raise ValueError("Spell target is outside verified terrain")
    dx, dy = target_cell[0] - actor.position[0], target_cell[1] - actor.position[1]
    distance = abs(dx) + abs(dy)
    if not rule["minimum"] <= distance <= rule["maximum"]:
        # fcj.a(PV,eVo,min,max,allowSelf,x,y) allows distance0 even outside
        # the range, only when the condition-selected fyP.cwE permits it.
        from .combat_self_cast import allows_self

        if distance != 0 or not allows_self(spell_id, context):
            raise ValueError("Spell target is outside native range")
    if rule["linear"] and dx != 0 and dy != 0:
        raise ValueError("Spell requires a straight line")
    # Native fcj -> fcr cast LOS tests height-adjusted rays. At the same
    # XYZ it succeeds without dynamic probes, even when the bare Sf ray
    # catalog has no visible zero-length pair. This is a cast policy, not a
    # fabricated static/dynamic LOS catalog entry.
    if (
        rule["line_of_sight"]
        and tuple(actor.position) != tuple(target_cell)
        and not line_of_sight(actor.position, target_cell, fight)
    ):
        raise ValueError("Spell target has no verified line of sight")
    target = next(
        (a for a in fight.actors.values() if a.hp > 0 and a.position == target_cell),
        None,
    )
    if rule["free_cell"] and target is not None:
        raise ValueError("Spell requires an unoccupied target cell")
    from .combat_spell_usage import validate_usage

    usage = validate_usage(
        fight, actor, spell_id, evaluation_level, target_cell, context
    )
    return dict(
        request,
        native_usage=usage,
        spell_id=spell_id,
        costs=costs,
        target_id=None if target is None else target.id,
        effect_ids=tuple(roots),
        evaluation_level=evaluation_level,
    )


def prepare_cast(
    body,
    character,
    fight,
    owner_id,
    deck_blob,
    *,
    wp,
    line_of_sight,
    select_effect,
    mitigate,
    complete=True,
):
    """Existing damage executor layered on the common spell validation."""
    prepared = prepare_spell_cast(
        body, character, fight, owner_id, deck_blob, wp=wp, line_of_sight=line_of_sight
    )
    request = decode_cast(body)
    actor_id, spell_id = prepared["actor_id"], prepared["spell_id"]
    actor = fight.actors[actor_id]
    costs = prepared["costs"]
    rule = normal_damage_profile(spell_id, actor.effective_level)
    target = fight.actors.get(prepared["target_id"])
    if target is None or target.team == actor.team or rule["free_cell"]:
        raise ValueError("This audited damage branch requires an enemy target")
    # Callback explicitly validates native branch conditions and effects. None
    # rejects unknown conditions instead of pretending they are unconditional.
    selected = select_effect(spell_id, rule, actor, target, fight)
    if isinstance(selected, dict):
        rule = selected
    elif selected is not True:
        raise ValueError("Native damage branch conditions are not supported")
    if complete and spell_id in (6260, 6261):
        raise ValueError("Mandatory native MP loss/theft is not implemented")
    damage = mitigate(rule["damage"], rule["element"], actor, target, fight)
    if type(damage) is not int or damage < 0 or damage > (1 << 31) - 1:
        raise ValueError("Invalid authoritative mitigated damage")
    return dict(
        request,
        spell_id=spell_id,
        target_id=target.id,
        costs=costs,
        generic_effect=rule["generic_effect"],
        element=rule["element"],
        base_damage=rule["damage"],
        damage=damage,
        complete=bool(complete),
        pending_side_effects=(
            "mp_theft" if spell_id == 6260 else "mp_loss" if spell_id == 6261 else None
        ),
    )
