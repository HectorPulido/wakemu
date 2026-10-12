"""Opt-in epistemic forecasts; authoritative execution has no masked areas."""
from contextlib import contextmanager
from contextvars import ContextVar

_UNOBSERVED_AREAS = ContextVar("unobserved_native_effect_areas", default=frozenset())


@contextmanager
def unobserved_area_forecast(identities):
    identities = frozenset(identities)
    if any(type(identity) is not int for identity in identities):
        raise ValueError("Invalid unobserved native area identities")
    token = _UNOBSERVED_AREAS.set(_UNOBSERVED_AREAS.get() | identities)
    try:
        yield
    finally:
        _UNOBSERVED_AREAS.reset(token)


def area_is_unobserved(identity):
    return identity in _UNOBSERVED_AREAS.get()
