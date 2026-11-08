"""Bind native runtime callbacks at their canonical shared Ready assembler."""
from dataclasses import dataclass
import time
from types import MethodType

from .combat_expiration_provider import OwnedExpirationFactory


_START = OwnedExpirationFactory.turn_start
_END = OwnedExpirationFactory.turn_end
_FIELDS = (
    "stats_serializer",
    "runtime_stats_serializer",
    "turn_end_provider",
    "turn_start_provider",
    "expiration_runtime_factory",
    "clock",
)


@dataclass(frozen=True)
class _NativeCallbacks:
    providers: tuple

    def __deepcopy__(self, memo):
        # RuntimeMessages preserves these exact injected service callbacks too.
        memo[id(self)] = self
        return self


def certify_ready_runtime(adapter, runtime, serializer, factory):
    """Called only by ready_transition with its locally constructed callbacks."""
    from .combat_session_adapter import CombatSessionAdapter
    from .combat_runtime_messages import RuntimeMessages

    if (
        type(adapter) is not CombatSessionAdapter
        or type(runtime) is not RuntimeMessages
        or type(factory) is not OwnedExpirationFactory
    ):
        return
    expected_start = factory.fight_start or factory.area_callbacks
    for name, enabled, method in (
        ("turn_start_provider", expected_start, _START),
        ("turn_end_provider", factory.fight_start, _END),
    ):
        callback = getattr(runtime, name)
        if not enabled:
            if callback is not None:
                return
        elif (
            type(callback) is not MethodType
            or callback.__self__ is not factory
            or callback.__func__ is not method
        ):
            return
    if (
        runtime.stats_serializer is not serializer
        or runtime.runtime_stats_serializer is not serializer
        or runtime.expiration_runtime_factory is not factory
        or runtime.clock is not time.monotonic
    ):
        return
    runtime._retained_gc_callbacks = _NativeCallbacks(
        tuple(getattr(runtime, name) for name in _FIELDS)
    )


def native_callbacks_known(runtime):
    """Replacement callbacks revoke proof; generic custom constructors do not issue it."""
    from .combat_runtime_messages import RuntimeMessages

    if type(runtime) is not RuntimeMessages:
        return False
    fields = vars(runtime)
    proof = fields.get("_retained_gc_callbacks")
    if proof is None:
        return (
            all(fields.get(name) is None for name in _FIELDS[:-1])
            and fields.get("clock") is time.monotonic
        )
    return (
        type(proof) is _NativeCallbacks
        and len(proof.providers) == len(_FIELDS)
        and all(
            fields.get(name) is provider
            for name, provider in zip(_FIELDS, proof.providers)
        )
        and type(fields.get("expiration_runtime_factory")) is OwnedExpirationFactory
    )


def capture_native_callbacks(runtime):
    """Capture existing provenance before a native constructor replaces services."""
    if not native_callbacks_known(runtime):
        return None
    return _NativeCallbacks(tuple(getattr(runtime, name) for name in _FIELDS))


def certify_rebound_runtime(runtime, provenance):
    """Finish an attested SDK handoff; callers verify its newly built callbacks."""
    from .combat_runtime_messages import RuntimeMessages

    if (
        type(provenance) is not _NativeCallbacks
        or type(runtime) is not RuntimeMessages
        or type(runtime.expiration_runtime_factory) is not OwnedExpirationFactory
        or runtime.clock is not time.monotonic
    ):
        return
    runtime._retained_gc_callbacks = _NativeCallbacks(
        tuple(getattr(runtime, name) for name in _FIELDS)
    )
