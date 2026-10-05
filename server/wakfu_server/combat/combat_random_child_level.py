"""eYx1076 / GS.p: one shared child SP, maximum exclusive."""
import math


def random_child_level(parameters, rng):
    if len(parameters) != 2 or any(
        type(v) is not int or not -(1 << 31) <= v < (1 << 31) for v in parameters
    ):
        raise ValueError("Native eYx requires two signed-int bounds")
    minimum, maximum = parameters
    if minimum == maximum:
        return minimum  # GS.p returns before accessing Random.
    width = ((maximum - minimum + (1 << 31)) % (1 << 32)) - (1 << 31)
    if width <= 0:
        raise ValueError("Native GS.p requires positive signed-int bound")
    if not callable(rng):
        raise ValueError("Transaction RNG required for native child level")
    draw = rng()
    if type(draw) is not float or not math.isfinite(draw) or not 0 <= draw < 1:
        raise ValueError("Native child-level unit draw required")
    # Owned server uniform draw; the native Java RNG seed stream is not copied.
    return minimum + int(draw * width)


def effective_child_level(override):
    return ((override + 32768) % 65536) - 32768
