"""eYA352: native symmetry center before inherited eYg cell expansion."""


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def symmetry_xy(parameters, caster, cell):
    if len(parameters) not in (1, 2) or any(type(v) is not int for v in parameters):
        raise ValueError("Unsupported native eYA parameters")
    # eYA.C tests exactly1; other first-parameter values mean caster pivot.
    pivot, point = (cell, caster) if parameters[0] == 1 else (caster, cell)
    x, y = pivot[:2]
    tx, ty = point[:2]
    angle = parameters[1] if len(parameters) == 2 else 1
    if angle == 0:
        return _i32(x - _i32(ty - y)), _i32(y + _i32(tx - x))
    if angle == 2:
        return _i32(x + _i32(ty - y)), _i32(y - _i32(tx - x))
    return _i32(_i32(2 * x) - tx), _i32(_i32(2 * y) - ty)


def symmetry_center(fight, parameters, caster, cell):
    if caster is None or cell is None:
        raise ValueError("Missing native eYA caster/cell authority")
    x, y = symmetry_xy(parameters, caster, cell)
    heights = {z for cx, cy, z in fight.walkable if (cx, cy) == (x, y)}
    if len(heights) > 1:
        raise ValueError("Native symmetry requires selected QI column altitude")
    if not heights:
        return None  # Native QI.R=false: bbH rejects application.
    z = next(iter(heights))
    return None if z == -32768 else (x, y, z)
