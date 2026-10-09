"""Synchronous triggering Qe.getValue, distinct from its event snapshot."""


def triggering_value(invocation):
    return triggering_descriptor_value(invocation.native_trigger_context)


def triggering_descriptor_value(descriptor):
    from .combat_final_modifier import triggering_runner_source
    from .combat_event_replay import NativeEventSource
    from .combat_trigger_value_modifier import NativeRunnerAmount

    if not isinstance(descriptor, dict):
        raise ValueError("Missing authoritative triggering eZR.getValue")
    value = descriptor.get("value")
    live = triggering_runner_source()
    if live is not None:
        if not isinstance(live, NativeEventSource):
            raise ValueError("Missing actual native triggering source")
        live.validate()
        if (live.uid, live.generic_effect, live.effect_action_id) != (
            descriptor.get("uid"),
            descriptor.get("generic_effect"),
            descriptor.get("effect_action_id"),
        ):
            raise ValueError("Native triggering source identity mismatch")
        runner = live.runner_modifier
        if runner is None:
            value = live.value
        elif (
            isinstance(runner, NativeRunnerAmount)
            and runner.uid == live.uid
            and runner.family == live.effect_action_id
        ):
            value = runner.value
        else:
            raise ValueError("Missing live native triggering amount")
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Missing authoritative triggering eZR.getValue")
    return value
