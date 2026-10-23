"""Trusted offline adapters for captured ordinary combat requests.

This module never imports a capsule-supplied symbol or opens a connection. The
caller restores catalogs/environment and controls wall time before entering it.
Only the restored runtime is mutated; service persistence and rewards are outside
this adapter's delivery boundary. A rejected action must be discarded by caller.
"""
import os
import random
from .combat_input_observation import InputReplayMismatch, replay_prepare_rng_argument


AUTHORITY_RECIPE = "ordinary-server-runtime-v1"
ACTION_FIELDS = {
    "player_spell": {"type", "body", "owner_id", "critical"},
    "player_weapon": {"type", "body", "owner_id", "critical"},
    "player_unarmed": {"type", "body", "owner_id", "critical"},
    "npc_spell": {"type", "action"},
    "move": {"type", "body", "owner_id"},
    "end_turn": {"type", "owner_id", "actor_id", "turn_id"},
    "end_server_turn": {"type", "actor_id", "turn_id"},
    "ack": {"type", "body"},
}


class ReproductionContextError(ValueError):
    """Captured authority is incomplete or incompatible with this recipe."""


def prepare_context(runtime, action, inputs, rng, clock):
    """Validate diagnostic context before entering a gameplay failure boundary."""
    try:
        _validate(action, inputs, rng, clock)
        for identity, monster in inputs["monsters"].items():
            if (
                not isinstance(monster, dict)
                or monster.get("id") != identity
                or any(
                    type(monster.get(field)) is not int
                    for field in ("ref", "level", "map_id")
                )
            ):
                raise ValueError("Incomplete captured monster descriptor")
        return bind_runtime(runtime, inputs, rng, clock)
    except (ValueError, KeyError, TypeError) as error:
        raise ReproductionContextError(str(error)) from error


def _validate(action, inputs, rng, clock):
    if not isinstance(action, dict) or action.get("type") not in ACTION_FIELDS:
        raise ValueError("Unsupported offline combat action")
    if set(action) != ACTION_FIELDS[action["type"]]:
        raise ValueError("Offline combat action fields do not match its recipe")
    if "body" in action and not isinstance(action["body"], bytes):
        raise ValueError("Captured client request must contain exact bytes")
    for field in ("owner_id", "actor_id", "turn_id"):
        if field in action and type(action[field]) is not int:
            raise ValueError("Invalid captured combat identity: " + field)
    if (
        "critical" in action
        and action["critical"] is not None
        and type(action["critical"]) is not bool
    ):
        raise ValueError("Invalid captured critical mode")
    if action["type"] == "player_unarmed" and action["critical"] is not False:
        raise ValueError("Unarmed reproduction requires the actual normal policy")
    if action["type"] == "npc_spell":
        request = action["action"]
        if not isinstance(request, dict) or set(request) != {
            "type",
            "spellId",
            "level",
            "targetId",
            "target",
        }:
            raise ValueError("Invalid standard native NPC request recipe")
    if (
        not isinstance(inputs, dict)
        or inputs.get("authority_recipe") != AUTHORITY_RECIPE
    ):
        raise ValueError("Unsupported or missing offline authority recipe")
    required = {
        "character",
        "monsters",
        "deck_blob",
        "player_characters",
        "deck_blobs",
        "map_id",
        "native_events",
        "area_callbacks",
    }
    if not required <= set(inputs):
        raise ValueError("Incomplete captured ordinary authority inputs")
    if not isinstance(rng, random.Random) or not callable(clock):
        raise ValueError("Explicit restored RNG and monotonic clock required")
    if any(
        type(inputs[name]) is not bool for name in ("native_events", "area_callbacks")
    ):
        raise ValueError("Explicit native boundary feature flags required")
    if inputs["area_callbacks"] != (
        os.environ.get("WAKFU_NATIVE_AREA_CALLBACKS", "1") == "1"
    ):
        raise ValueError("Captured area policy differs from restored environment")
    if not isinstance(inputs["character"], dict) or type(inputs["map_id"]) is not int:
        raise ValueError("Invalid captured character/map authority")
    if inputs["character"].get("map_id") != inputs["map_id"]:
        raise ValueError("Captured character/map authority mismatch")
    characters, decks = inputs["player_characters"], inputs["deck_blobs"]
    if (
        not isinstance(characters, dict)
        or not isinstance(decks, dict)
        or set(characters) != set(decks)
    ):
        raise ValueError("Every captured player needs its exact deck")
    identity = inputs["character"].get("id")
    if (
        characters.get(identity) != inputs["character"]
        or decks.get(identity) != inputs["deck_blob"]
    ):
        raise ValueError("Captured caster differs from player/deck authority")
    if not isinstance(inputs["monsters"], dict) or not isinstance(
        inputs["deck_blob"], bytes
    ):
        raise ValueError("Invalid captured monster/deck authority")
    for identity, character in characters.items():
        if (
            type(identity) is not int
            or not isinstance(character, dict)
            or character.get("id") != identity
            or not isinstance(decks[identity], bytes)
        ):
            raise ValueError("Invalid captured player/deck identity")


def bind_runtime(runtime, inputs, rng, clock):
    """Reconstruct only the explicit ordinary-server-runtime-v1 providers."""
    from .combat_actor import actual_actor_stats, actual_monster_actor_stats
    from .combat_summon_stats import registered_summon_stats
    from .combat_server_spell import (
        server_runtime,
        prepare_server_turn_start,
        prepare_server_turn_end,
    )
    from .combat_area_transaction import prepare_area_movement

    character = inputs["character"]
    monsters = inputs["monsters"]
    deck = inputs["deck_blob"]
    owned = {
        "player_characters": inputs["player_characters"],
        "deck_blobs": inputs["deck_blobs"],
        "rng": rng,
    }

    def boundary_owned():
        # Choose before prepare_* enters rollback_external_rng; internal and
        # externally supplied streams have different rollback ownership.
        return dict(owned, rng=replay_prepare_rng_argument("server_runtime", rng))

    def serialize(actor, fight):
        if actor.id in getattr(fight, "native_summon_registrations", {}):
            return registered_summon_stats(actor, fight, inputs["map_id"])
        if getattr(actor, "native_summon_source", None) is not None:
            raise ValueError("Missing captured summon registration")
        if (
            not isinstance(actor.effect_stats, dict)
            or not isinstance(actor.effect_maxima, dict)
            or 4 not in actor.effect_stats
            or 4 not in actor.effect_maxima
        ):
            raise ValueError("Missing authoritative combat WP snapshot")
        kwargs = {
            "wp_current": actor.effect_stats[4],
            "wp_maximum": actor.effect_maxima[4],
            "fight": fight,
        }
        if actor.controlled:
            source = inputs["player_characters"].get(actor.id)
            if source is None:
                raise ValueError("Missing captured player snapshot")
            return actual_actor_stats(source, actor, fight.id, **kwargs)
        source = monsters.get(actor.id)
        if source is None:
            raise ValueError("Missing captured monster snapshot")
        return actual_monster_actor_stats(
            source, actor, fight.id, direction=3, **kwargs
        )

    runtime.clock = clock
    # The graph snapshot deliberately omits callable movement authority. Bind
    # the same actor authority as the actual transaction factory before any
    # voluntary movement (which evaluates tackle before area callbacks).
    factory, _ = server_runtime(
        character,
        monsters,
        deck,
        action_id=runtime.action_id + 1,
        critical=False,
        **owned,
    )
    runtime.fight.native_rail_movement_authority = (
        factory.native_rail_movement_authority
    )
    runtime.runtime_stats_serializer = serialize
    runtime.stats_serializer = lambda actor: serialize(actor, runtime.fight)
    runtime.expiration_runtime_factory = lambda *, action_id: server_runtime(
        character,
        monsters,
        deck,
        action_id=action_id,
        critical=False,
        **boundary_owned(),
    )[0]
    runtime.turn_start_provider = (
        (
            lambda fight, **boundary: prepare_server_turn_start(
                character,
                monsters,
                fight,
                deck,
                native_events=inputs["native_events"],
                area_callbacks=inputs["area_callbacks"],
                **boundary_owned(),
                **boundary,
            )
        )
        if inputs["native_events"] or inputs["area_callbacks"]
        else None
    )
    runtime.turn_end_provider = (
        (
            lambda fight, **boundary: prepare_server_turn_end(
                character, monsters, fight, deck, **boundary_owned(), **boundary
            )
        )
        if inputs["native_events"]
        else None
    )
    movement_provider = (
        (
            lambda fight, **boundary: prepare_area_movement(
                character, monsters, fight, deck, **boundary_owned(), **boundary
            )
        )
        if inputs["area_callbacks"]
        else None
    )
    return serialize, movement_provider


def unarmed_entry_resources(body, character, fight):
    """The real dispatcher's empty-slot and WP checks, before UID selection."""
    from .combat_weapon import decode_request
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.breed_resources import live_wp

    request = decode_request(body)
    if request["item_uid"] != -1:
        raise InputReplayMismatch("Unarmed recipe requires native item UID -1")
    selected = character["builds"].get(character.get("active_build_index", 0), {})
    if any(
        row["slot"] == 15
        for row in validate_sheet(
            character, bytes.fromhex(selected.get("equipment", "")), strict=False
        )
    ):
        raise ValueError("Unarmed action requires the owned weapon slot to be empty")
    return live_wp(fight, request["actor_id"])


def prepare_reproduced_unarmed(
    body,
    character,
    monsters,
    fight,
    owner_id,
    *,
    action_id,
    effect_uid,
    wp,
    player_characters,
    deck_blobs,
    rng=None
):
    """Run the existing native unarmed transaction, never a damage substitute."""
    from .combat_melee import prepare_server_unarmed

    if type(effect_uid) is not int or not 0 < effect_uid <= 2**60:
        raise InputReplayMismatch("Missing actual unarmed UID observation")
    return prepare_server_unarmed(
        body,
        character,
        monsters,
        fight,
        owner_id,
        unarmed=True,
        wp_current=wp[0],
        wp_maximum=wp[1],
        action_id=action_id,
        effect_uid=effect_uid,
        critical_chance=0,
        caster_running_effects=(),
        target_running_effects=(),
        caster_bonuses={},
        target_bonuses={},
        mitigate=lambda damage, element, source, target, state: damage,
        player_characters=player_characters,
        deck_blobs=deck_blobs,
        rng=replay_prepare_rng_argument("server_runtime", rng),
    )


def execute(runtime, action, inputs, rng, clock, *, prepared_context=None):
    """Execute one captured request through production prepare/commit APIs.

    Packet bytes are the real delivery batch, including registered deaths. This
    is the runtime action boundary, not shared-session routing or fight rewards.
    Ready is deliberately unsupported: its pre-runtime creation boundary needs
    a separate captured initialization recipe.
    """
    serialize, movement_provider = (
        prepare_context(runtime, action, inputs, rng, clock)
        if prepared_context is None
        else prepared_context
    )
    previous_sequence = runtime.fight.sequence
    transaction = None
    kind = action["type"]
    if kind in ("player_spell", "player_weapon", "player_unarmed", "npc_spell"):
        from .combat_spell_commit import commit_spell_transaction

        common = {
            "action_id": runtime.action_id + 1,
            "rng": replay_prepare_rng_argument(
                "npc_spell"
                if kind == "npc_spell"
                else "server_runtime"
                if kind == "player_unarmed"
                else "player_spell.before_critical"
                if kind == "player_spell"
                else "player_weapon.before_critical",
                rng,
            ),
            "player_characters": inputs["player_characters"],
            "deck_blobs": inputs["deck_blobs"],
        }
        if kind == "player_unarmed":
            wp = unarmed_entry_resources(
                action["body"], inputs["character"], runtime.fight
            )
            transaction = prepare_reproduced_unarmed(
                action["body"],
                inputs["character"],
                inputs["monsters"],
                runtime.fight,
                action["owner_id"],
                effect_uid=inputs.get("unarmed_effect_uid"),
                wp=wp,
                **common,
            )
        elif kind == "npc_spell":
            from .combat_npc_spell import prepare_npc_spell

            transaction = prepare_npc_spell(
                runtime.fight,
                action["action"],
                inputs["character"],
                inputs["monsters"],
                inputs["deck_blob"],
                **common,
            )
        else:
            from .combat_los import authoritative_visible
            from .combat_server_spell import prepare_server_spell
            from .combat_weapon import prepare_server_weapon

            prepare = (
                prepare_server_spell
                if kind == "player_spell"
                else prepare_server_weapon
            )
            transaction = prepare(
                action["body"],
                inputs["character"],
                inputs["monsters"],
                runtime.fight,
                action["owner_id"],
                inputs["deck_blob"],
                critical=action["critical"],
                line_of_sight=lambda origin, target, fight: authoritative_visible(
                    inputs["map_id"],
                    origin,
                    target,
                    fight,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in fight.actors.values()
                        if actor.hp > 0
                    },
                ),
                **common,
            )
        packets = commit_spell_transaction(
            runtime, transaction, stats_serializer=serialize
        )
    elif kind == "move":
        from .combat_movement_runtime import apply_client

        packets, _ = apply_client(
            runtime,
            action["owner_id"],
            action["body"],
            runtime.stats_serializer,
            runtime_stats_serializer=serialize,
            area_provider=movement_provider,
        )
        packets = runtime.prepare_delivery(packets)
    elif kind == "end_turn":
        packets = runtime.end_turn(
            action["owner_id"], action["actor_id"], action["turn_id"]
        )
    elif kind == "end_server_turn":
        packets = runtime.end_server_turn(action["actor_id"], action["turn_id"])
    else:
        packets = runtime.acknowledge_turn(action["body"])
    from .combat_death import newly_registered_death_messages

    packets = tuple(packets) + tuple(
        newly_registered_death_messages(runtime, after_sequence=previous_sequence)
    )
    events = tuple(
        event for event in runtime.fight.events if event["sequence"] > previous_sequence
    )
    return {
        "transaction": transaction,
        "state": runtime.fight,
        "events": events,
        "packets": packets,
        "plan": transaction.plan if transaction is not None else None,
        "outcomes": transaction.outcomes if transaction is not None else (),
    }
