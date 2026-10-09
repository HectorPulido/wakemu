"""Original eNY diagonal criterion arithmetic, distinct from fcj alignment."""
from .combat_casting_range import int32


def native_diagonal(source, target):
    """Resolved eII.d coordinates; explicit native null yields false."""
    if source is None or target is None:
        return False
    for position in (source, target):
        if (
            not isinstance(position, (tuple, list))
            or len(position) < 2
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in position[:2]
            )
        ):
            raise ValueError("Invalid native diagonal XY coordinate")
    # eNY: int subtraction -> double pow2 -> Java d2i saturation.
    squared = [min(2147483647, int32(target[i] - source[i]) ** 2) for i in (0, 1)]
    return squared[0] == squared[1]
