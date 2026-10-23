"""Capability adapter for the existing native eXt damage execution path.

Static parsing never substitutes actor HP, a rounding draw, a triggering value
or a calculated damage amount. The existing handler owns those runtime values.
"""
from collections.abc import Mapping


# Exactly the flags already consumed by NativeDamageHandler and its parameter
# interpreter. Ordering flags still require a separately identity-bound proof.
_FLAGS = frozenset((2, 3, 4, 5, 6, 8, 14, 15, 17, 22, 23, 24, 28, 31, 34))


def parse(effect):
    from .combat_damage_parameters import (
        damage_parameter_specification,
        interpret_damage_parameters,
    )

    from .combat_damage_contracts import DAMAGE_FAMILIES

    if effect.get("effect_class") not in DAMAGE_FAMILIES:
        raise ValueError("The eXt capability adapter requires the damage family")
    level = effect.get("_capability_level")
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Missing native damage capability level")
    flags = effect.get("native_effect_flags")
    if (
        not isinstance(flags, (list, tuple))
        or any(type(flag) is not int for flag in flags)
        or len(flags) != len(set(flags))
        or set(flags) - _FLAGS
    ):
        raise ValueError("Unsupported native damage flags")
    if type(effect.get("native_localization_enabled")) is not bool:
        raise ValueError("Missing native damage localization authority")
    specification = damage_parameter_specification(effect["parameters"], level)
    requirements = ["native_damage_execution", "native_runner_lifecycle"]
    if specification["base_kind"]:
        parsed = dict(specification)
        parsed["base_parameter"] = parsed.pop("base")
        requirements.append("native_damage_hp_and_rounding")
    else:

        def no_rounding():
            raise ValueError("Static damage parsing cannot draw transaction RNG")

        parsed = interpret_damage_parameters(
            effect["parameters"],
            level,
            hp_context=None,
            rng=no_rounding,
        )
    if set(flags) & {8, 14}:
        requirements.append("native_damage_ordering_identity")
    return parsed, tuple(requirements), (), None


def execution_context(factory, route):
    """Prove installed handler and real dynamic operand providers, without calls."""
    from .combat_damage_handler import NativeDamageHandler

    if route is None or route.handler_type is not NativeDamageHandler:
        return False
    contexts = factory.contexts
    # The ordinary authority deliberately samples block after calculation.
    # Missing block RNG must not masquerade as a preselected nonblock result.
    if not all(
        callable(getattr(contexts, key, None))
        for key in ("damage", "stat", "rounding", "damage_block")
    ):
        return None
    return True


def verify_initialized(dispatcher, preview, plan):
    """Attest actual damage handler/event/retention ownership after construction."""
    from .combat_damage_handler import NativeDamageHandler
    from .combat_ordinary_events import OrdinaryDamageEvents

    retention = getattr(dispatcher, "native_retention", None)
    handlers = getattr(dispatcher, "handlers", None)
    if retention is None or not isinstance(handlers, Mapping):
        return False
    wrapped = handlers.get(1)
    raw = getattr(wrapped, "native_wrapped_handler", None)
    if (
        type(raw) is not NativeDamageHandler
        or getattr(wrapped, "native_retention_owner", None) is not retention
        or raw.retention is not retention
        or raw.fight is not preview
        or retention.fight is not preview
        or retention.plan is not plan
    ):
        return False
    events = raw.event_lifecycle
    if (
        type(events) is not OrdinaryDamageEvents
        or events.preview is not preview
        or events.plan is not plan
        or events.retention is not retention
        or events.replay is not getattr(dispatcher, "replay_event", None)
    ):
        return False
    bindings = getattr(dispatcher, "operation_contracts", None)
    binding = bindings.get(1) if isinstance(bindings, Mapping) else None
    return binding is not None and binding.handler is wrapped
