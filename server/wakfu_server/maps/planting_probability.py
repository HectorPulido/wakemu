"""World-owned validation and comparison of one authoritative planting roll."""

import math


def succeeds(probability, draw):
    """Compare one server-owned uniform draw, without rounding the chance."""
    if (
        any(
            type(value) not in (int, float)
            or not 0 <= value <= 1
            or not math.isfinite(value)
            for value in (probability, draw)
        )
        or draw == 1
    ):
        raise ValueError("Invalid authoritative planting roll")
    return draw < probability
