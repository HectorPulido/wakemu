"""Detach canonical native providers before any fallible private planning."""

from copy import deepcopy
import time
import sys
from types import FunctionType

from ..native.native_stats import NativeStats


def _oracle_boundary(callback, boundary, runtime, provider):
    """Accept the SDK's committed live boundary with its owned source data."""
    owner = getattr(callback, "__self__", None)
    kind = type(owner)
    module = sys.modules.get(kind.__module__)
    expected = (
        "live_start_boundary"
        if boundary == "turn_start_provider"
        else "live_end_boundary"
    )
    if (
        kind.__name__ != "NativeOracle"
        or not kind.__module__.endswith(".native.native_oracle")
        or getattr(module, "NativeOracle", None) is not kind
        or getattr(callback, "__func__", None) is not vars(kind).get(expected)
        or getattr(getattr(owner, "runtime", None), "fight", None) is None
        or owner.runtime.fight.id != runtime.fight.id
        or set(owner.characters) != set(provider.characters)
        or owner.decks != provider.decks
        or owner.viewer_id not in provider.characters
    ):
        return None
    for identity, character in owner.characters.items():
        captured = provider.characters[identity]
        if any(
            character.get(key) != captured.get(key)
            for key in ("id", "account_id", "map_id", "instance_id")
        ):
            return None
    if any(
        runtime.fight.rift_monsters.get(identity) != source
        for identity, source in owner.monsters.items()
    ):
        return None
    return owner


def rift_sources(runtime, provider):
    """Verify complete ordinary wave sources and owned lifecycle callbacks."""
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
    from wakfu_server.combat_ordinary_reinforcement_sources import (
        current_monster_sources,
    )

    fight = runtime.fight
    state = getattr(fight, "rift_wave_state", None)
    if (
        type(provider) is not OwnedExpirationFactory
        or not isinstance(state, dict)
        or type(state.get("instance_id")) is not int
        or state["instance_id"] <= 0
    ):
        raise ValueError("Background rift requires its owned frozen instance")
    viewer = provider.characters.get(provider.actor_id)
    if viewer is None or any(
        character.get("instance_id") != state["instance_id"]
        or character.get("map_id") != viewer.get("map_id")
        for character in provider.characters.values()
    ):
        raise ValueError("Background rift character sources left their instance")
    for name, method in (
        ("turn_start_provider", OwnedExpirationFactory.turn_start),
        ("turn_end_provider", OwnedExpirationFactory.turn_end),
    ):
        callback = getattr(runtime, name, None)
        if (
            callback is not None
            and (
                getattr(callback, "__self__", None) is not provider
                or getattr(callback, "__func__", None) is not method
            )
            and _oracle_boundary(callback, name, runtime, provider) is None
        ):
            raise ValueError("Background rift lifecycle callback is not owned")
    sources = getattr(fight, "rift_monsters", None)
    registrations = getattr(fight, "native_summon_registrations", {})
    ordinary = {
        identity
        for identity, actor in fight.actors.items()
        if not actor.controlled and identity not in registrations
    }
    if (
        not isinstance(sources, dict)
        or set(sources) != ordinary
        or any(
            sources.get(identity) != source
            for identity, source in provider.monsters.items()
        )
    ):
        raise ValueError("Background rift ordinary source authority changed")
    # This existing producer verifies fresh identities against committed wave
    # receipts and the exact native world/admission creation ledger.
    current = current_monster_sources(fight, provider.monsters, map_id=viewer["map_id"])
    if set(current) != ordinary:
        raise ValueError("Background rift source roster is incomplete")
    return current


def rift_admission_reason(shared, provider):
    """Keep socket-owned or unqualified Rift publishers on their existing path."""
    context = getattr(shared, "join_context", None)
    accepted = (
        context.get("rift_accepted_action") if isinstance(context, dict) else None
    )
    # The installed checkpoint provider receives all mutable fight/runtime
    # authority explicitly. A session closure must never cross into a worker.
    if not isinstance(accepted, FunctionType) or accepted.__closure__ is not None:
        return "rift_providers_unqualified"
    try:
        rift_sources(shared.runtime, provider)
    except (ValueError, TypeError, AttributeError, KeyError):
        return "rift_providers_unqualified"
    return None


def bind_private_sources(runtime, session):
    """Bind only a private candidate while its shared authority is locked."""
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory

    provider = getattr(runtime, "expiration_runtime_factory", None)
    if type(provider) is not OwnedExpirationFactory:
        raise ValueError("Background native turn requires owned lifecycle providers")
    if getattr(runtime, "clock", time.monotonic) is not time.monotonic:
        raise ValueError("Background native turn requires the canonical clock")
    oracle_callbacks = {}
    if getattr(runtime.fight, "rift_wave_state", None) is not None:
        for name in ("turn_start_provider", "turn_end_provider"):
            callback = getattr(runtime, name, None)
            owner = (
                _oracle_boundary(callback, name, runtime, provider)
                if callback is not None
                else None
            )
            if owner is not None:
                oracle_callbacks[name] = owner
    provider = deepcopy(provider)
    if getattr(runtime.fight, "rift_wave_state", None) is not None:
        provider.monsters = deepcopy(
            rift_sources(runtime, runtime.expiration_runtime_factory)
        )
    viewer = provider.characters.get(session.character_id)
    if viewer is None or viewer.get("account_id") != session.account_id:
        raise ValueError("Missing owned background viewer authority")
    serializer = NativeStats(
        characters=provider.characters,
        monsters=provider.monsters,
        fight_id=runtime.fight.id,
        registrations=getattr(runtime.fight, "native_summon_registrations", {}),
        map_id=viewer["map_id"],
    )
    runtime.expiration_runtime_factory = provider
    private_oracles = {}
    for name, method in (
        ("turn_start_provider", provider.turn_start),
        ("turn_end_provider", provider.turn_end),
    ):
        if getattr(runtime, name, None) is None:
            continue
        original = oracle_callbacks.get(name)
        if original is None:
            setattr(runtime, name, method)
            continue
        # RuntimeMessages deliberately shares callback services on deepcopy.
        # Construct a complete private oracle before rebinding its lifecycle.
        oracle = private_oracles.get(id(original))
        if oracle is None:
            oracle = type(original)(
                runtime,
                characters=original.characters,
                monsters=provider.monsters,
                decks=original.decks,
                excluded_decks=original.excluded_decks,
                viewer_id=original.viewer_id,
                flags=original.flags,
                outcome_features=original.outcome_features_provider,
            )
            private_oracles[id(original)] = oracle
        setattr(
            runtime,
            name,
            getattr(
                oracle,
                "live_start_boundary"
                if name == "turn_start_provider"
                else "live_end_boundary",
            ),
        )
    runtime.stats_serializer = serializer
    runtime.runtime_stats_serializer = serializer
