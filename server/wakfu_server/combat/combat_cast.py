"""Pure cast validation; terrain LOS and effect conditions remain authoritative.

Common request validation uses native definitions for all class spells and
accepts self and empty-cell targets. Damage execution remains a separate layer
with a limited audited set. No state changes occur during validation; unknown
conditional costs are rejected rather than treated as unconditional.
"""

from wakfu_server.character_levels import MAX_CHARACTER_LEVEL
from wakfu_server import native_catalog as protocol_catalog
from wakfu_server.paths import DATA_ROOT
import json
import struct
from wakfu_server.spells import validate_deck
from .combat_parameters import parameter_value
from wakfu_server.spell_audit import catalog as effect_catalog

_RULES = protocol_catalog.load(DATA_ROOT / "combat-spell-rules.json")["spells"]


def decode_cast(body):
    """13260/cpm payload, exactly actorUID, spellUID, x/y/z (26 bytes)."""
    if len(body) != 26:
        raise ValueError("Invalid cpm payload length")
    actor_id, spell_uid, x, y, z = struct.unpack(">qqiih", body)
    return dict(actor_id=actor_id, spell_uid=spell_uid, target=(x, y, z))


def normal_damage_profile(spell_id, level):
    """Native normal branch values; caller must verify its effect conditions."""
    if str(spell_id) not in _RULES or not 1 <= level <= MAX_CHARACTER_LEVEL:
        raise ValueError("No audited spell damage profile")
    rule = _RULES[str(spell_id)]
    if level > len(rule["levels"]):
        raise ValueError("Missing native spell damage profile level")
    minimum, maximum, _ = rule["levels"][level - 1]
    effect = effect_catalog()["effects"][str(rule["generic_effect"])]
    damage = parameter_value(effect["parameters"], 0, level)
    return dict(rule, minimum=minimum, maximum=maximum, damage=damage)


def resolve_owned_spell_action(request, character, fight, owner_id, deck_blob):
    """Resolve one active owned UID and level before resource or RNG work."""
    actor_id = request["actor_id"]
    actor = fight.actors.get(actor_id)
    from .combat_effective_control import effective_input_owner

    if (
        fight.phase != "active"
        or fight.current is not actor
        or actor is None
        or effective_input_owner(fight, actor) != owner_id
        or actor.hp <= 0
    ):
        raise ValueError("Caster is not the owned active actor")
    return _resolve_actor_spell_action(
        request, character, fight, actor, deck_blob, owner_id
    )


def _resolve_actor_spell_action(request, character, fight, actor, deck_blob, owner_id):
    """Resolve the actual owned book after the caller proves control authority."""
    actor_id = actor.id
    uid = request["spell_uid"]
    spell_id = uid & 0xFFFFFFFF
    from .combat_spell_grant import granted_spells

    from .combat_spell_grant_book import grant_record, removed_raw_uids

    temporary = grant_record(fight, actor_id, spell_id)
    granted = uid == spell_id and temporary is not None and temporary["uid"] == uid
    from .combat_morph_spellbook import morph_record, resolve_morph_action

    if morph_record(fight, actor_id) is not None:
        if str(actor_id) in getattr(fight, "native_companion_sources", {}):
            from .combat_companions import resolve_action

            reference, level = resolve_action(fight, actor, character, owner_id, uid)
            return actor, reference, level
        if actor_id != character["id"]:
            from .combat_summon_spellbook import validate_controlled_owner

            validate_controlled_owner(fight, actor, character["id"], owner_id)
        reference, level = resolve_morph_action(fight, actor_id, uid)
        return actor, reference, level
    if actor_id != character["id"] and actor_id in getattr(
        fight, "native_controller_action_books", {}
    ):
        from .combat_controller_transfer import resolve_controller_action

        if granted:
            return actor, spell_id, temporary["level"]
        reference, level = resolve_controller_action(fight, actor, owner_id, uid)
        return actor, reference, level
    if str(actor_id) in getattr(fight, "native_companion_sources", {}):
        from .combat_companions import resolve_action

        reference, level = resolve_action(fight, actor, character, owner_id, uid)
        return actor, reference, level
    summon_level = None
    if actor_id != character["id"]:
        from .combat_summon_spellbook import (
            resolve_controlled_action,
            validate_controlled_owner,
        )

        if granted:
            validate_controlled_owner(fight, actor, character["id"], owner_id)
        else:
            if uid in removed_raw_uids(fight, actor_id):
                raise ValueError("Native spell object was removed from the actor book")
            spell_id, summon_level = resolve_controlled_action(
                fight, actor, character["id"], owner_id, uid
            )
    elif not granted:
        if uid != (actor_id << 32) | spell_id:
            raise ValueError("Spell UID belongs to another actor or expired grant")
        deck = validate_deck(
            deck_blob, character["breed"], character["level"], character=character
        )
        if spell_id not in deck["active"]:
            raise ValueError("Spell is absent from current deck")
    evaluation_level = (
        temporary["level"]
        if granted
        else summon_level
        if summon_level is not None
        else actor.effective_level
    )
    return actor, spell_id, evaluation_level


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
    diagnostic=None,
):
    """Validate ownership, book, resources, native range and terrain only.

    Returning a plan does not execute or validate the effect tree. In
    particular it does not assert that the selected actor can receive effects.
    """
    request = decode_cast(body)
    actor, spell_id, evaluation_level = resolve_owned_spell_action(
        request, character, fight, owner_id, deck_blob
    )
    return _prepare_resolved_spell_cast(
        request,
        character,
        fight,
        deck_blob,
        actor,
        spell_id,
        evaluation_level,
        wp=wp,
        line_of_sight=line_of_sight,
        conditional_context=conditional_context,
        diagnostic=diagnostic,
    )


def _prepare_resolved_spell_cast(
    request,
    character,
    fight,
    deck_blob,
    actor,
    spell_id,
    evaluation_level,
    *,
    wp,
    line_of_sight,
    conditional_context=None,
    diagnostic=None,
):
    """Common native casting validation after explicit book/control resolution."""
    from .combat_conditional_costs import ConditionalCostContext
    from .combat_native_spell_casting import definition as native_definition
    from .combat_casting_range import resolve_range

    context = (
        conditional_context(request, fight) if callable(conditional_context) else None
    )
    snapshot = getattr(actor, "spell_ap_cost_modifiers", None)
    if isinstance(context, ConditionalCostContext):
        context, snapshot = context.conditions, context.ap_modifiers_by_category
    from .combat_cast_diagnostics import casting_diagnostics

    try:
        owner_deck = validate_deck(
            deck_blob, character["breed"], character["level"], character=character
        )
    except ValueError:
        # Diagnostics do not add an ordinary-deck gate to grants or morphs.
        owner_deck = None
    rule = {}
    try:
        rule = native_definition(spell_id, evaluation_level, context, snapshot)
        rule = resolve_range(rule, actor, context)
    except ValueError as error:
        if hasattr(error, "native_casting_selection"):
            rule = dict(rule, native_casting_selection=error.native_casting_selection)
        error.cast_diagnostics = casting_diagnostics(
            fight, actor, request, spell_id, evaluation_level, rule, context, owner_deck
        )
        raise
    costs, roots = rule["costs"], rule["roots"]
    diagnostics = casting_diagnostics(
        fight, actor, request, spell_id, evaluation_level, rule, context, owner_deck
    )
    if diagnostic is not None:
        if not callable(diagnostic):
            raise ValueError("Casting diagnostic callback must be callable")
        from copy import deepcopy

        diagnostic(deepcopy(diagnostics))
    try:
        result = _validate_target(
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
    except ValueError as error:
        error.cast_diagnostics = diagnostics
        raise
    result["cast_diagnostics"] = diagnostics
    return result


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
    from .combat_ap_property_cost import require_native_ap_cost

    actors = getattr(context, "actors", None)
    caster_context = actors.get("caster") if hasattr(actors, "get") else None
    require_native_ap_cost(
        costs["ap"], getattr(caster_context, "fight_properties", None)
    )
    if actor.ap < costs["ap"] or actor.mp < costs["mp"] or wp < costs["wp"]:
        error = ValueError("Insufficient authoritative spell resources")
        error.cast_validation_code = "insufficient_resources"
        error.native_resource_diagnostic = {
            "available": {"ap": actor.ap, "mp": actor.mp, "wp": wp},
            "required": {name: costs[name] for name in ("ap", "mp", "wp")},
            "deficits": {
                name: costs[name] - available
                for name, available in (("ap", actor.ap), ("mp", actor.mp), ("wp", wp))
                if costs[name] > available
            },
        }
        raise error
    from .combat_spell_resource_costs import extra_costs, validate_extra_resources

    approved_extra_deltas = extra_costs(costs.get("extra_resource_values", {}), actor)
    validate_extra_resources(actor, approved_extra_deltas)
    costs["extra_resource_deltas"] = approved_extra_deltas
    target_cell = request["target"]
    query = getattr(context, "native_casting_query", None)
    if not callable(query):
        raise ValueError("Missing authoritative shared native casting producer")
    decision = query(rule, spell_id, evaluation_level)
    if not isinstance(decision, dict) or decision.get("result") != "twD":
        reason = decision.get("result") if isinstance(decision, dict) else "unknown"
        error = ValueError("Native spell casting eligibility rejected: " + str(reason))
        error.native_casting_result = reason
        if isinstance(decision, dict):
            error.native_casting_diagnostic = decision.get("diagnostic")
        raise error
    if decision.get("aligned") is not True:
        error = ValueError("Native spell casting alignment/path rejected")
        error.cast_validation_code = "alignment_rejected"
        raise error
    from .combat_spell_usage import validate_usage

    usage = validate_usage(
        fight, actor, spell_id, evaluation_level, target_cell, context
    )
    return dict(
        request,
        native_usage=usage,
        native_casting_selection=rule.get("native_casting_selection"),
        native_casting_diagnostic=decision.get("diagnostic"),
        native_casting_flags={
            key: rule[key]
            for key in (
                "minimum",
                "maximum",
                "line_of_sight",
                "linear",
                "diagonal",
                "linear_path",
                "path_option",
                "free_cell",
                "range_modifiable",
                "allow_self",
                "forbid_QI_P",
            )
        },
        spell_id=spell_id,
        costs=costs,
        target_id=decision["target_id"],
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
    conditional_context=None,
):
    """Existing damage executor layered on the common spell validation."""
    prepared = prepare_spell_cast(
        body,
        character,
        fight,
        owner_id,
        deck_blob,
        wp=wp,
        line_of_sight=line_of_sight,
        conditional_context=conditional_context,
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
