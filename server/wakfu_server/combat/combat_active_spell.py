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
def active_spell_scope(fight, reference, *, level=None):
    active_spell_id(fight)
    if type(reference) is not int or not 0 < reference < (1 << 31):
        raise ValueError("Invalid owned active spell reference")
    if level is not None and (type(level) is not int or not 0 <= level <= 32767):
        raise ValueError("Invalid owned active fyG evaluation level")
    previous = fight.native_active_spell_id
    previous_container = getattr(fight, "native_active_spell_container", None)
    fight.native_active_spell_id = reference
    fight.native_active_spell_container = (
        None
        if level is None
        else dict(present=True, is_spell=True, spell_id=reference, level=level)
    )
    try:
        yield
    finally:
        fight.native_active_spell_id = previous
        fight.native_active_spell_container = previous_container


def active_spell_container(fight):
    """Actual PN.bah -> fcS.baR/fXw, independently from any trigger PL."""
    if active_spell_id(fight) == -1:
        return {"present": False}  # Proven null current PZ.
    descriptor = getattr(fight, "native_active_spell_container", None)
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("present") is not True
        or descriptor.get("is_spell") is not True
        or descriptor.get("spell_id") != fight.native_active_spell_id
        or type(descriptor.get("level")) is not int
    ):
        raise ValueError("Missing actual active PZ.baR fyG container")
    return dict(descriptor)
