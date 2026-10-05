"""Bounded, request-owned combat diagnostics; never serialize private contexts."""
from contextlib import contextmanager
from contextvars import ContextVar

_trace = ContextVar("combat_diagnostic_trace", default=None)
_FIELDS = frozenset(
    {
        "effect_reference",
        "effect_class",
        "level",
        "caster_id",
        "target_id",
        "cell",
        "state_uid",
        "ancestors",
        "status",
        "reason",
        "exception_type",
        "elapsed_ms",
        "criteria",
    }
)


@contextmanager
def combat_diagnostic_scope(sink, *, limit=256):
    if not callable(sink) or type(limit) is not int or limit < 1:
        raise ValueError("Diagnostic sink and positive event limit required")
    trace = {"sink": sink, "limit": limit, "emitted": 0, "dropped": 0}
    token = _trace.set(trace)
    try:
        yield
    finally:
        _trace.reset(token)
        sink(
            event="combat_effect_trace_summary",
            effects_logged=trace["emitted"],
            effects_omitted=trace["dropped"],
        )


def diagnostics_enabled():
    return _trace.get() is not None


def effect_step(**fields):
    trace = _trace.get()
    if trace is None:
        return
    if set(fields) - _FIELDS:
        raise ValueError("Unapproved combat diagnostic fields")
    if trace["emitted"] >= trace["limit"]:
        trace["dropped"] += 1
        return
    trace["emitted"] += 1
    trace["sink"](event="combat_effect", **fields)
