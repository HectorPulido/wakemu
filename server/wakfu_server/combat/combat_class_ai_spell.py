"""Real class-book casting for native server-controlled original players.

Class ownership and ordinary player input authority remain separate from AI control.
"""
import random
import struct
from .combat_effective_control import effective_server_controlled
from .combat_cast import (
    decode_cast,
    _resolve_actor_spell_action,
    _prepare_resolved_spell_cast,
)
from .combat_spell_transaction import _prepare_spell_transaction


def require_class_ai(fight, character, deck_blob):
    actor = fight.current
    if (
        fight.phase != "active"
        or actor is None
        or actor.hp <= 0
        or fight.actors.get(actor.id) is not actor
        or actor.controlled is not True
        or character.get("id") != actor.id
        or not hasattr(fight, "native_controller_registry")
        or not effective_server_controlled(fight, actor)
    ):
        raise ValueError("Missing actual server-controlled class actor authority")
    from wakfu_server.spells import validate_deck

    validate_deck(
        deck_blob, character["breed"], character["level"], character=character
    )
    return actor


def prepare_class_ai_plan(
    body,
    character,
    fight,
    owner_id,
    deck_blob,
    *,
    wp,
    line_of_sight,
    conditional_context=None
):
    actor = require_class_ai(fight, character, deck_blob)
    request = decode_cast(body)
    if request["actor_id"] != actor.id:
        raise ValueError("Class AI action belongs to another actor")
    actor, spell, level = _resolve_actor_spell_action(
        request, character, fight, actor, deck_blob, owner_id
    )
    return _prepare_resolved_spell_cast(
        request,
        character,
        fight,
        deck_blob,
        actor,
        spell,
        level,
        wp=wp,
        line_of_sight=line_of_sight,
        conditional_context=conditional_context,
    )


def prepare_class_ai_spell(
    fight,
    action,
    character,
    monsters,
    deck_blob,
    *,
    action_id,
    line_of_sight,
    player_characters,
    deck_blobs,
    rng=None
):
    actor = require_class_ai(fight, character, deck_blob)
    if (
        not isinstance(player_characters, dict)
        or not isinstance(deck_blobs, dict)
        or player_characters.get(actor.id) != character
        or deck_blobs.get(actor.id) != deck_blob
    ):
        raise ValueError("Class AI snapshot is not the actual combat participant")
    spell = action.get("spellId")
    if action.get("type") != "cast" or type(spell) is not int:
        raise ValueError("Missing actual owned class AI action reference")
    actions = canonical_class_actions(fight, actor, character, deck_blob)
    if spell not in actions:
        raise ValueError("Class AI action is absent from actual owned book")
    uid = actions[spell]["uid"]
    target = action.get("target")
    if (
        not isinstance(target, (list, tuple))
        or len(target) != 3
        or any(type(value) is not int for value in target)
    ):
        raise ValueError("Missing actual class AI target coordinates")
    body = struct.pack(">qqiih", actor.id, uid, *target)
    request = decode_cast(body)
    _, owned_spell, level = _resolve_actor_spell_action(
        request, character, fight, actor, deck_blob, character.get("account_id")
    )
    if (
        spell != owned_spell
        or type(action.get("level")) is not int
        or action["level"] != level
    ):
        raise ValueError("Class AI spell/level differs from actual owned book")
    from .combat_server_spell import server_runtime
    from .combat_critical import choose_critical, spell_critical_available

    rng = random.Random() if rng is None else rng
    # Replay and caller RNG rollback must cover critical choice as well as effects.
    before_rng = rng.getstate()
    try:
        decision = choose_critical(
            actor,
            rng=rng,
            mode="auto",
            critical_available=spell_critical_available(spell, level),
        )
        factory, adapter = server_runtime(
            character,
            monsters,
            deck_blob,
            action_id=action_id,
            critical=decision.critical,
            rng=rng,
            player_characters=player_characters,
            deck_blobs=deck_blobs,
        )
        transaction = _prepare_spell_transaction(
            body,
            character,
            fight,
            None,
            deck_blob,
            wp_current=actor.effect_stats[4],
            action_id=action_id,
            line_of_sight=line_of_sight,
            runtime_factory=factory,
            conditional_context=lambda request, preview: adapter.cast_condition(
                preview, request
            ),
            critical=decision.critical,
            plan_builder=prepare_class_ai_plan,
        )
        if transaction.plan["target_id"] != action.get("targetId"):
            raise ValueError("Class AI target differs from validated native target")
        transaction.plan["critical_decision"] = decision.diagnostic()
        return transaction
    except BaseException:
        rng.setstate(before_rng)
        raise


def class_ai_capabilities(fight, character, deck_blob):
    actor = require_class_ai(fight, character, deck_blob)
    from .combat_ai_capabilities import describe_spell
    from copy import deepcopy

    return [
        dict(deepcopy(describe_spell(ref, entry["level"])), spellUid=entry["uid"])
        for ref, entry in sorted(
            canonical_class_actions(fight, actor, character, deck_blob).items()
        )
    ]


def require_class_ai_producer(fight, actor, authority):
    """Prove real class input snapshots before a native transfer can enable AI.

    Only the shared ordinary server runtime supplies these sources. Lightweight
    authority callbacks without class books remain unsupported before mutation.
    """
    from .combat_summon import RegisteredSummonAuthority
    from .combat_ordinary_authority import OrdinaryActorAuthority
    from .combat_spell_level import NativeSpellBook
    from wakfu_server.spells import validate_deck

    ordinary = (
        authority.ordinary
        if isinstance(authority, RegisteredSummonAuthority)
        else authority
    )
    if not isinstance(ordinary, OrdinaryActorAuthority):
        raise ValueError("Unsupported native eWD player AI capability producer")
    character = ordinary.characters.get(actor.id)
    deck = None if ordinary.deck_blobs is None else ordinary.deck_blobs.get(actor.id)
    metadata = authority(fight, actor)
    if (
        not isinstance(character, dict)
        or character.get("id") != actor.id
        or not isinstance(deck, bytes)
        or actor.controlled is not True
        or metadata.is_player is not True
        or not isinstance(metadata.native_spellbook, NativeSpellBook)
        or metadata.native_spellbook.player_character is not True
    ):
        raise ValueError("Unsupported native eWD player AI capability producer")
    validate_deck(deck, character["breed"], character["level"], character=character)
    # Resolve actual candidate objects before enabling AI, including current
    # grants and transformations; resource/target legality stays per-action.
    from .combat_morph_spellbook import morph_record
    from .combat_spell_grant import granted_spells

    morph = morph_record(fight, actor.id)
    uids = (
        set(morph["levels"]) - morph["removed_raw_uids"]
        if morph is not None
        else {
            (actor.id << 32) | ref
            for ref in validate_deck(
                deck, character["breed"], character["level"], character=character
            )["active"]
        }
    )
    uids.update(granted_spells(fight, actor.id))
    for uid in uids:
        _resolve_actor_spell_action(
            {"actor_id": actor.id, "spell_uid": uid},
            character,
            fight,
            actor,
            deck,
            None,
        )
    return character, deck


def canonical_class_actions(fight, actor, character, deck_blob):
    """Keep the native oracle's grant-first raw UID contract, adding morphs.

    The public native action carries a reference and level. Native eWn grants
    already replace that reference's oracle entry; keep that explicit source
    precedence, never infer a UID from an unowned reference or requested level.
    """
    from wakfu_server.spells import validate_deck
    from .combat_spell_grant import granted_spells
    from .combat_spell_grant_book import grant_record
    from .combat_morph_spellbook import morph_record

    if (
        fight.actors.get(actor.id) is not actor
        or character.get("id") != actor.id
        or actor.controlled is not True
    ):
        raise ValueError("Missing actual class action owner")
    deck = validate_deck(
        deck_blob, character["breed"], character["level"], character=character
    )
    morph = morph_record(fight, actor.id)
    candidates = (
        {ref: ref for ref in morph["levels"] if ref not in morph["removed_raw_uids"]}
        if morph is not None
        else {ref: (actor.id << 32) | ref for ref in deck["active"] if ref}
    )
    for ref in granted_spells(fight, actor.id):
        candidates[ref] = grant_record(fight, actor.id, ref)["uid"]
    result = {}
    for ref, uid in candidates.items():
        _, actual, level = _resolve_actor_spell_action(
            {"actor_id": actor.id, "spell_uid": uid},
            character,
            fight,
            actor,
            deck_blob,
            None,
        )
        if actual != ref or actual in result:
            raise ValueError("Ambiguous actual native class action identity")
        result[actual] = {"uid": uid, "level": level}
    return result
