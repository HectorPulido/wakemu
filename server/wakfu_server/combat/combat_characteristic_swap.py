"""Native eZy ordered PA current operations and captured runner payload."""
from .combat_effects import _integer, _varint


def swap_characteristics(first, second, *, current, shift, captured=None, remove=False):
    """Callbacks must address the same actual target PA objects, including aliases."""
    if any(
        type(value) is not int or not -128 <= value <= 127 for value in (first, second)
    ):
        raise ValueError("Missing native eZy signed characteristic IDs")
    if type(remove) is not bool:
        raise ValueError("Missing native eZy execution branch")
    if captured is None:
        if remove:
            raise ValueError("Native eZy removal requires captured current values")
        captured = (current(first), current(second))
    if (
        not isinstance(captured, (tuple, list))
        or len(captured) != 2
        or any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in captured
        )
    ):
        raise ValueError("Missing native eZy captured PA currents")
    before_first, before_second = captured
    subtract_first, add_first = (
        (before_second, before_first) if remove else (before_first, before_second)
    )
    subtract_second, add_second = (
        (before_first, before_second) if remove else (before_second, before_first)
    )
    # Each call is observable; direct assignment loses clamping, frozen PA
    # behavior, aliasing and notification order from eZy.c/bbR.
    shift(first, subtract_first, True)
    shift(first, add_first, False)
    shift(second, subtract_second, True)
    shift(second, add_second, False)
    return tuple(captured)


def swap_additional_payload(first, second, captured):
    if any(
        type(value) is not int or not -128 <= value <= 127 for value in (first, second)
    ):
        raise ValueError("Missing native eZy signed characteristic IDs")
    if (
        not isinstance(captured, (list, tuple))
        or len(captured) != 2
        or any(
            type(value) is not int or not -(1 << 31) <= value < (1 << 31)
            for value in captured
        )
    ):
        raise ValueError("Missing native eZy captured PA currents")
    additional = b"".join(
        _integer(field, value)
        for field, value in (
            (10, captured[0]),
            (12, first),
            (19, second),
            (20, captured[1]),
        )
    )
    return _varint(8 << 3 | 2) + _varint(len(additional)) + additional
