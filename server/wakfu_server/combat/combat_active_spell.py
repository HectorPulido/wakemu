"""eJn/eII.o: current fight PZ.ayn; separate from trigger or PL identity."""
from contextlib import contextmanager


def active_spell_id(fight):
    if not hasattr(fight, "native_active_spell_id"):
        raise ValueError("Missing authoritative native active spell context")
    value = fight.native_active_spell_id
    if value is None:
        return -1  # eJn null fight/PZ sentinel.
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Invalid native PZ spell reference")
    return value


@contextmanager
def active_spell_scope(fight, reference):
    active_spell_id(fight)
    if type(reference) is not int or not 0 < reference < (1 << 31):
        raise ValueError("Invalid owned active spell reference")
    previous = fight.native_active_spell_id
    fight.native_active_spell_id = reference
    try:
        yield
    finally:
        fight.native_active_spell_id = previous
