"""Native static fcj alignment, independently of ordinary cast eligibility."""
from wakfu_server.combat_casting_range import int32
from wakfu_server.combat_conditions import UnknownCondition


def native_casting_alignment(
    source, target, *, linear, diagonal, linear_path, path_option, path_query=None
):
    """Consume selected fyP flags and an authoritative Sn traversal callback.

    source is caster.baM, not the physical efR path origin. path_query must
    bind the actual efR, footprint, QI, target exclusion and cleanup policies;
    it receives only the selected cwN flag. No occupancy is inferred here.
    """
    if any(
        type(flag) is not bool for flag in (linear, diagonal, linear_path, path_option)
    ):
        raise ValueError("Missing selected native static casting flags")
    if not linear and not diagonal:
        return True
    for position in (source, target):
        if (
            not isinstance(position, (tuple, list))
            or len(position) < 2
            or any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in position[:2]
            )
        ):
            raise ValueError("Missing native static casting XY coordinates")
    linear_accepted = linear and (source[0] == target[0] or source[1] == target[1])
    if linear_accepted and linear_path:
        if not callable(path_query):
            raise UnknownCondition("Missing native Sn casting traversal authority")
        result = path_query(path_option)
        if type(result) is not bool:
            raise UnknownCondition("Missing native Sn casting traversal result")
        linear_accepted = result
    if not diagonal or linear_accepted:
        return linear_accepted

    # Unlike eNY's squared-double criterion, fcj uses Java Math.abs(int).
    def java_abs(value):
        return value if value == -(1 << 31) else abs(value)

    return java_abs(int32(target[0] - source[0])) == java_abs(
        int32(target[1] - source[1])
    )
