"""Native fcj alignment predicate over resolved eII.d positions."""


def native_alignment(source, target):
    """Compare resolved XY coordinates; native null coordinates are false."""
    if source is None or target is None:
        return False
    for position in (source, target):
        if (
            not isinstance(position, (tuple, list))
            or len(position) < 2
            or any(type(value) is not int for value in position[:2])
        ):
            raise ValueError("Invalid native alignment XY coordinate")
    return source[0] == target[0] or source[1] == target[1]
