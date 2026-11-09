"""Observe the native callback once; never substitute damage or facing rules."""
from contextlib import contextmanager
from contextvars import ContextVar

_SAMPLES = ContextVar("native_damage_observations", default=None)


@contextmanager
def capture():
    samples = []
    token = _SAMPLES.set(samples)
    try:
        yield samples
    finally:
        _SAMPLES.reset(token)


def current():
    return _SAMPLES.get()


from ..context.native_context import encode, NativeGraph


def observe(callback, samples):
    def damage(preview, plan, effect, invocation):
        context = callback(preview, plan, effect, invocation)
        # Freeze the entire callback data now. Effects, actors and invocation
        # can change later in the native chain; a final-state direction is not
        # evidence of the context used for this arithmetic calculation.
        try:
            sample = encode(
                dict(
                    context=context,
                    effect=effect,
                    invocation=invocation,
                    plan=plan,
                    source=preview.actors[invocation.caster_id],
                    target=preview.actors[invocation.target_id],
                    basis="native_damage_context_callback",
                )
            )
        except Exception as error:
            # Observation must not reject a native callback that succeeded.
            # Declare the missing graph explicitly; never claim completeness.
            sample = dict(
                observationUnavailable=True,
                complete=False,
                errorType=type(error).__name__,
                detail=str(error),
            )
        samples.append(sample)
        return context

    return damage


def evidence(samples):
    result = []
    for sample in samples:
        if sample.get("observationUnavailable"):
            result.append(dict(sample, basis="native_damage_context_capture_failed"))
            continue
        graph = NativeGraph(sample)
        root = graph.data["root"]
        context = graph.field(root, "context")
        invocation = graph.field(root, "invocation")
        effect = graph.field(root, "effect")

        def value(reference, name):
            return graph.plain(graph.field(reference, name))

        observed = value(context, "localization")
        enabled = value(effect, "native_localization_enabled")
        executable = value(context, "executable")
        result.append(
            dict(
                effectReference=value(invocation, "reference"),
                level=value(invocation, "level"),
                casterId=value(invocation, "caster_id"),
                targetId=value(invocation, "target_id"),
                observedLocalization=observed,
                localizationEnabled=enabled,
                executable=executable,
                arithmeticLocalization=(
                    (observed if enabled else "FRONT") if executable else None
                ),
                basis="native_damage_context_callback",
            )
        )
    return result
