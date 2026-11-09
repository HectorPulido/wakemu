"""Renew Ready provenance only at exact native SDK service constructors."""
from types import MethodType

from wakfu_server.combat_retained_gc_authority import (
    capture_native_callbacks,
    certify_rebound_runtime,
    _START,
    _END,
)
from wakfu_server.combat_expiration_provider import OwnedExpirationFactory
from . import native_stats


def renew_native_callbacks(runtime, provenance):
    if provenance is None:
        return
    from . import native_oracle

    serializer = runtime.stats_serializer
    if (
        type(serializer) is not native_stats._GC_STATS_TYPE
        or native_stats.NativeStats is not native_stats._GC_STATS_TYPE
        or runtime.runtime_stats_serializer is not serializer
        or serializer.fight_id != runtime.fight.id
    ):
        return
    for name, original in native_stats._GC_STATS_METHODS.items():
        if getattr(type(serializer), name) is not original or name in vars(serializer):
            return
    factory = runtime.expiration_runtime_factory
    if type(factory) is not OwnedExpirationFactory:
        return
    for field, factory_method, oracle_method in (
        ("turn_start_provider", _START, native_oracle._GC_ORACLE_START),
        ("turn_end_provider", _END, native_oracle._GC_ORACLE_END),
    ):
        callback = getattr(runtime, field)
        if callback is None:
            continue
        if type(callback) is not MethodType:
            return
        owner = callback.__self__
        if owner is factory:
            if callback.__func__ is not factory_method:
                return
        else:
            if (
                type(owner) is not native_oracle._GC_ORACLE_TYPE
                or native_oracle.NativeOracle is not native_oracle._GC_ORACLE_TYPE
                or callback.__func__ is not oracle_method
                or native_oracle.native_boundary_fight_id(owner) != runtime.fight.id
            ):
                return
            for name, original in (
                ("live_start_boundary", native_oracle._GC_ORACLE_START),
                ("live_end_boundary", native_oracle._GC_ORACLE_END),
                ("start_boundary", native_oracle._GC_ORACLE_START_IMPL),
                ("end_boundary", native_oracle._GC_ORACLE_END_IMPL),
                ("factory", native_oracle._GC_ORACLE_FACTORY),
            ):
                if getattr(type(owner), name) is not original or name in vars(owner):
                    return
    certify_rebound_runtime(runtime, provenance)
