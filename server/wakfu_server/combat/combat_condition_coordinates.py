"""Native eLT/eLU/eLW: signed coordinates and Long.MIN_VALUE for null eHg.

Target aBn precedes actor lookup; selector defaults to caster unless the one
literal string equals target ignoring case. Resolver belongs to the adapter.
"""


def native_coordinate(axis, position):
    if axis not in ("x", "y", "z"):
        raise ValueError("Unknown native coordinate axis")
    if position is None:
        return -(1 << 63)
    if not isinstance(position, (tuple, list)) or len(position) != 3:
        raise ValueError("Missing native 3D position")
    value = position["xyz".index(axis)]
    bits = 16 if axis == "z" else 32
    if type(value) is not int or not -(1 << (bits - 1)) <= value < (1 << (bits - 1)):
        raise ValueError("Native coordinate exceeds signed axis bounds")
    return value
