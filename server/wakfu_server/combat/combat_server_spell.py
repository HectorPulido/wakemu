"""Common ordinary PVE cast entry, with no class/spell whitelist.

Critical branch is explicit until its native server roll is reconstructed.
All random draws belong to a fresh transaction; unsupported mandatory effects
reject without committing combat resources or sending partial packets.
"""
import json
import random
from functools import lru_cache
from .combat_static_catalogs import CompiledEffects, characteristic_registry
from wakfu_server.paths import DATA_ROOT
from .spells import validate_deck
from .spell_audit import catalog, states_catalog, costs_catalog
from .combat_ordinary_authority import OrdinaryActorAuthority, ordinary_cast_authority
from .combat_runtime_adapter import NativeServerRuntimeAdapter
from .combat_effect_runtime import NativeEffectRuntimeFactory
from .combat_native_timing_context import NativeEffectTimingProvider
from .combat_spell_transaction import prepare_spell_transaction


@lru_cache(maxsize=1)
def compiled_runtime_catalog():
    return CompiledEffects(catalog()["effects"], states_catalog())


def prewarm_runtime_catalogs():
    """Load/validate static assets before opening listeners, never bind a fight."""
    from .combat_actor_snapshot import native_actor_catalog
    from .combat_ordinary_authority import native_property_catalog
    from .combat_retained_runtime import native_retained_metadata
    from .combat_event_costs import cost_catalog
    from .combat_characteristic_conditions import native_aliases
    from .combat_conditional_costs import native_catalog
    compiled = compiled_runtime_catalog()
    for loader in (characteristic_registry, native_actor_catalog,
                   native_property_catalog, native_retained_metadata,
                   cost_catalog, costs_catalog, native_aliases, native_catalog):
        loader()
    return {"effect_definitions": len(compiled.effects)}


def server_runtime(character, monsters, deck_blob, *, action_id, critical, rng=None):
    """One transaction-owned RNG shared by ordinary and relative decisions."""
    transaction_rng = random.Random() if rng is None else rng
    deck = validate_deck(deck_blob, character["breed"], character["level"])
    actors = OrdinaryActorAuthority(
        characters={character["id"]: character},
        monsters=monsters,
        decks={character["id"]: frozenset(deck["active"] + deck["passive"])},
        excluded_decks={character["id"]: frozenset()},
    )
    states = states_catalog()
    authority = ordinary_cast_authority(
        actors=actors,
        timing=NativeEffectTimingProvider(states),
        rng=transaction_rng,
        critical=critical,
    )
    adapter = NativeServerRuntimeAdapter(actor_authority=actors, cast=authority)
    factory = NativeEffectRuntimeFactory(
        effects=catalog()["effects"],
        state_catalog=states,
        characteristic_registry=characteristic_registry(),
        compiled_effects=compiled_runtime_catalog(),
        action_id=action_id,
        contexts=adapter.contexts(),
        displacement_authority=actors,
    )
    from .combat_relative_probability import RelativeGroupAuthority

    factory.relative_group_children = RelativeGroupAuthority(
        effects=factory.effects,
        actor_authority=actors,
        condition_context=adapter.condition,
        draw_integer=lambda total: transaction_rng.randint(1, total),
        draw_fraction=lambda fraction: transaction_rng.random() < fraction,
    )
    return factory, adapter


def prepare_server_spell(
    body,
    character,
    monsters,
    fight,
    owner_id,
    deck_blob,
    *,
    action_id,
    line_of_sight,
    critical,
    rng=None
):
    factory, adapter = server_runtime(
        character, monsters, deck_blob, action_id=action_id, critical=critical, rng=rng
    )
    actor = fight.actors[character["id"]]
    if not isinstance(actor.effect_stats, dict) or 4 not in actor.effect_stats:
        raise ValueError("Initialize native characteristics before casting")
    return prepare_spell_transaction(
        body,
        character,
        fight,
        owner_id,
        deck_blob,
        wp_current=actor.effect_stats[4],
        action_id=action_id,
        line_of_sight=line_of_sight,
        runtime_factory=factory,
        conditional_context=lambda request, preview: adapter.cast_condition(
            preview, request
        ),
        critical=critical,
    )


def prepare_server_initialization(
    character, monsters, fight, owner_id, deck_blob, *, action_id, rng=None
):
    """Initialize own innates/passives on an ACTIVE preview, without guessed events.

    Caller commits preview and emits packets only after this returns. Placement
    readiness/lifecycle must be handled by the caller before invoking it.
    """
    from .combat_class_initialization import plan, initialize_transaction

    factory, _ = server_runtime(
        character, monsters, deck_blob, action_id=action_id, critical=False, rng=rng
    )
    states = states_catalog()
    actor = fight.actors.get(character["id"])
    if actor is None:
        raise ValueError("Missing owned class initialization actor")
    owned = dict(
        character, x=actor.position[0], y=actor.position[1], z=actor.position[2]
    )
    initial = plan(owned, deck_blob, catalog(), states)
    return initialize_transaction(fight, initial, factory, states, owner_id=owner_id)
