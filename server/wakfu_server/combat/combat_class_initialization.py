"""Installed breed innates and owned deck-passive initialization plan.

big.doS/big.a(eGH) directly applies innate triples; no guessed init event is
fired. Passive roots are given to an explicit native subscription installer,
not immediately executed while their triggers are ignored.
"""
from wakfu_server import native_catalog as protocol_catalog
import json
from functools import lru_cache
from dataclasses import dataclass
from wakfu_server.paths import DATA_ROOT
from wakfu_server.spells import SPELLS, validate_deck
from .combat_effect_dispatch import EffectInvocation, UnsupportedEffectExecution

BREEDS = {
    r["breed"]: r
    for r in protocol_catalog.load(DATA_ROOT / "breed-innate-definitions.json")[
        "breeds"
    ]
}


@dataclass(frozen=True)
class InnateState:
    reference: int
    level: int
    protected: bool


@dataclass(frozen=True)
class ClassInitialization:
    actor_id: int
    breed: int
    innates: tuple
    passive_invocations: tuple
    passive_sources: tuple


@lru_cache(maxsize=1)
def level_zero_catalog():
    """Installed fG(short0) roots; level1 and the last level are not substitutes."""
    from .combat_captured_dependencies import (
        captured_zero_catalog,
        merge_zero_component,
    )

    existing = protocol_catalog.load(DATA_ROOT / "native-class-spell-level-zero.json")
    captured = captured_zero_catalog()
    merged = {
        **existing,
        **{
            component: merge_zero_component(
                existing.get(component, {}), captured[component]
            )
            for component in ("spells", "casting", "effects")
        },
    }
    from .combat_triggered_dependencies import zero_catalog as triggered_zero_catalog

    triggered = triggered_zero_catalog()
    if triggered is not None:
        merged.update(
            {
                component: merge_zero_component(merged[component], triggered[component])
                for component in ("spells", "casting", "effects")
            }
        )
    from .combat_morph_dependencies import zero_catalog as morph_zero_catalog

    morph = morph_zero_catalog()
    if morph is not None:
        merged.update(
            {
                component: merge_zero_component(merged[component], morph[component])
                for component in ("spells", "casting", "effects")
            }
        )
    return merged


def plan(character, deck_blob, spell_catalog, state_catalog, *, zero_catalog=None):
    breed, level = character["breed"], character["level"]
    definition = BREEDS.get(breed)
    if definition is None:
        raise ValueError("Unknown installed breed definition")
    deck = validate_deck(deck_blob, breed, level)
    effective = level if deck["level_cap"] == -1 else min(level, deck["level_cap"])
    innates = []
    for row in definition["innate_states"]:
        reference = row["reference"]
        state_level = (
            effective if row["level_parameter"] == -1 else row["level_parameter"]
        )
        if str(reference) not in state_catalog["states"]:
            raise UnsupportedEffectExecution("Missing installed innate state")
        innates.append(InnateState(reference, state_level, row["protected"]))
    passive = []
    sources = []
    for reference in deck["passive"]:
        if reference == 0:
            continue
        owned = SPELLS.get(reference)
        if (
            owned is None
            or owned["breed"] not in (breed, -2)
            or owned["kind"] != "passive"
        ):
            raise ValueError("Foreign or nonpassive deck spell")
        spell = spell_catalog["spells"].get(str(reference))
        if spell is None:
            raise UnsupportedEffectExecution("Missing native passive spell tree")
        if effective == 0:
            zero = level_zero_catalog() if zero_catalog is None else zero_catalog
            record = zero.get("spells", {}).get(str(reference))
            if not isinstance(record, list) or len(record) != 3:
                raise UnsupportedEffectExecution(
                    "Missing native passive level-zero roots"
                )
            minimum, maximum, roots = record
            if not isinstance(roots, list) or any(
                type(root) is not int
                or str(root) not in spell_catalog.get("effects", {})
                for root in roots
            ):
                raise UnsupportedEffectExecution(
                    "Missing native passive level-zero effect closure"
                )
        else:
            minimum, maximum, roots = spell["levels"][effective - 1]
        if minimum > maximum:
            raise UnsupportedEffectExecution("Invalid native passive level bounds")
        for effect in roots:
            sources.append(reference)
            passive.append(
                EffectInvocation(
                    effect,
                    effective,
                    character["id"],
                    character["id"],
                    (character["x"], character["y"], character["z"]),
                )
            )
    return ClassInitialization(
        character["id"], breed, tuple(innates), tuple(passive), tuple(sources)
    )


def install(initialization, *, install_innate, install_passive):
    """Callbacks own ONE transaction preview and explicit native timer/flags.

    install_innate(actor_id,reference,level,protected) must create owned carrier
    and children. install_passive(spell_reference,invocation) must preserve native trigger
    subscriptions. No silently skipped callback or synthesized304 is allowed.
    """
    if not callable(install_innate) or not callable(install_passive):
        raise ValueError("Missing native initialization installers")
    results = []
    for state in initialization.innates:
        results.append(
            install_innate(
                initialization.actor_id, state.reference, state.level, state.protected
            )
        )
    for source, invocation in zip(
        initialization.passive_sources, initialization.passive_invocations
    ):
        results.append(install_passive(source, invocation))
    return tuple(results)


def initialize_transaction(
    fight, initialization, runtime_factory, state_catalog, *, owner_id
):
    """Return an owned preview and outbox; caller alone commits/emits.

    Native direct eWu has no applying effect/container. Permanent breed states
    use untouched native time sentinels. All other clocks remain unsupported
    here; passive roots use their real spell container and normal dispatcher.
    """
    from copy import deepcopy
    from .combat_definitions import state_profile
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload

    preview = deepcopy(fight)
    actor = preview.actors.get(initialization.actor_id)
    if actor is None or actor.hp <= 0 or preview.phase != "active":
        raise ValueError("Class initialization requires an owned active fighter")
    if (
        type(owner_id) is not int
        or owner_id <= 0
        or not actor.controlled
        or actor.owner_id != owner_id
    ):
        raise ValueError("Class initialization requires an owned character actor")
    marker = getattr(preview, "native_class_initializations", {})
    if initialization.actor_id in marker:
        raise ValueError("Fighter class effects are already initialized")
    packets = []
    dispatcher, outbox = runtime_factory(
        preview, {"native_retained_container": {"present": False}}
    )
    state = dispatcher.native_state_handler
    retention = dispatcher.native_retention
    with preview.effect_resolution():
        for innate in initialization.innates:
            profile = state_profile(state_catalog, innate.reference, innate.level)
            if profile["duration"] != -1 or profile["realtime_duration"] > 0:
                raise UnsupportedEffectExecution(
                    "Innate clock needs an audited initial timeline"
                )
            invocation = EffectInvocation(
                2226, innate.level, actor.id, actor.id, actor.position
            )
            context = StateCarrierContext(
                -1,
                profile["realtime_duration"],
                False,
                None,
                None,
                False,
                False,
                False,
                0,
                native_time_payload(realtime_remaining=profile["realtime_duration"]),
            )
            retention.open_state(invocation)
            try:
                state.apply_reference(
                    None,
                    invocation,
                    innate.reference,
                    innate.level,
                    carrier_context=context,
                    protected=innate.protected,
                )
            finally:
                retention.close_state(invocation)
    packets.extend(outbox)
    # Keep source order, without registering a passive more than once.
    current_source = None
    with preview.effect_resolution():
        for source, invocation in zip(
            initialization.passive_sources, initialization.passive_invocations
        ):
            if source != current_source:
                if current_source is not None:
                    packets.extend(outbox)
                dispatcher, outbox = runtime_factory(
                    preview, {"spell_id": source, "evaluation_level": invocation.level}
                )
                current_source = source
            dispatcher.execute(invocation)
        if current_source is not None:
            packets.extend(outbox)
    marker[actor.id] = dict(
        breed=initialization.breed,
        innates=[s.reference for s in initialization.innates],
    )
    preview.native_class_initializations = marker
    return preview, tuple(packets)
