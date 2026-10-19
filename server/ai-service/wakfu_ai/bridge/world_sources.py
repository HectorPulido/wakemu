"""Detach canonical native providers before any fallible private planning."""

from copy import deepcopy
import time

from ..native.native_stats import NativeStats


def bind_private_sources(runtime, session):
    """Bind only a private candidate while its shared authority is locked."""
    from wakfu_server.combat_expiration_provider import OwnedExpirationFactory

    provider = getattr(runtime, "expiration_runtime_factory", None)
    if type(provider) is not OwnedExpirationFactory:
        raise ValueError("Background native turn requires owned lifecycle providers")
    if getattr(runtime.fight, "rift_wave_state", None) is not None:
        raise ValueError("Background rift lifecycle providers are not qualified")
    if getattr(runtime, "clock", time.monotonic) is not time.monotonic:
        raise ValueError("Background native turn requires the canonical clock")
    provider = deepcopy(provider)
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
    if runtime.turn_start_provider is not None:
        runtime.turn_start_provider = provider.turn_start
    if runtime.turn_end_provider is not None:
        runtime.turn_end_provider = provider.turn_end
    runtime.stats_serializer = serializer
    runtime.runtime_stats_serializer = serializer
