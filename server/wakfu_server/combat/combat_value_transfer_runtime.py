"""Common eYy865 children, using actual final runner callbacks/eVt identity."""
from dataclasses import replace
from .combat_runner_callbacks import runner_value_scope
from .combat_value_transfer import (
    value_transfer_specification,
    execute_value_transfer,
    transfer_value_context,
)
from .combat_native_events import validate_group_registration_flags


def execute_runtime_transfer(dispatcher, effect, values, invocation, *, ancestors):
    from .combat_effect_dispatch import UnsupportedEffectExecution

    children = effect["children"]
    if len(children) != 2 or invocation.target_id is None:
        raise UnsupportedEffectExecution(
            "Native865 requires exactly two children and original actor"
        )
    if dispatcher.group_retention is None or not callable(
        dispatcher.transfer_probability
    ):
        raise UnsupportedEffectExecution(
            "Native865 requires authoritative eVt and stochastic rounding"
        )
    validate_group_registration_flags(
        effect["native_effect_flags"],
        active=dispatcher.group_retention.fight.phase == "active",
        effect=effect,
        reference=invocation.reference,
    )
    child_level, context = dispatcher.group_retention.child_level_context(
        effect, values, invocation, default_level=None, event_activation=True
    )
    position = dispatcher.actor_position(invocation.target_id)
    first = replace(
        invocation,
        reference=children[0],
        level=child_level,
        cell=position,
        native_context_hex=context.hex(),
        native_value_scope=None,
        base_uid=None,
        native_explicit_target=True,
    )
    outcomes = []

    def execute_first(capture):
        first_effect = dispatcher.effects[str(first.reference)]
        handler = dispatcher.handlers.get(first_effect["effect_class"])
        if getattr(handler, "native_runner_value_verified", False) is not True:
            raise UnsupportedEffectExecution(
                "Native865 first child has no audited final runner callback"
            )
        with runner_value_scope(lambda inv, value: capture(value)) as token:
            outcomes.append(
                dispatcher.execute(
                    replace(first, native_value_scope=token), ancestors=ancestors
                )
            )

    def execute_second(value, on_original_target):
        second = replace(
            first,
            reference=children[1],
            target_id=invocation.target_id
            if on_original_target
            else invocation.caster_id,
            native_context_hex=transfer_value_context(context, value).hex(),
            native_value_scope=None,
        )
        result = dispatcher.execute(second, ancestors=ancestors)
        outcomes.append(result)
        return result

    skip = False
    if children[1] == 101395:  # Exact native eYy.c exception, not a spell whitelist.
        if not callable(dispatcher.transfer_skip_second):
            raise UnsupportedEffectExecution(
                "Native865 requires faO category authority"
            )
        skip = dispatcher.transfer_skip_second(effect, invocation)
        if type(skip) is not bool:
            raise ValueError("Native faO category decision required")
    execute_value_transfer(
        value_transfer_specification(values["parameters"]),
        execute_first=execute_first,
        execute_second=execute_second,
        probability=dispatcher.transfer_probability,
        skip_second=skip,
    )
    return any(outcomes)
