"""Original Sf integer raster and ordered Vz topology, with no per-ray Java.

The narrowly validated program is exported from the installed Sf.bfZ class.
Only its integer/local/field/control operations and m/bfX hooks are supported.
Static results are cached; live actor blockers are evaluated by the caller.
"""
from functools import lru_cache
import gzip
import json
from .paths import DATA_ROOT
from .combat_parameters import _float32


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _short(value):
    return ((value + 32768) % 65536) - 32768


@lru_cache(maxsize=1)
def ray_program():
    data = json.loads((DATA_ROOT / "native-los-ray-program.json").read_text())
    if data.get("schema") != "native-Sf-bfZ-int-v1":
        raise ValueError("Unsupported native LOS raster program")
    return tuple(tuple(row) for row in data["instructions"])


@lru_cache(maxsize=4)
def topology_columns(map_id):
    path = DATA_ROOT / "native-los-topology" / f"{map_id}.json.gz"
    if not path.is_file():
        raise ValueError("Missing native LOS topology columns for this map")
    with gzip.open(path, "rt") as stream:
        data = json.load(stream)
    if data.get("map_id") != map_id or data.get("schema") != "native-Sf-Vz-columns-v1":
        raise ValueError("Native LOS topology identity mismatch")
    shared = {}
    columns = {}
    for x, y, values in data["columns"]:
        surfaces = tuple(map(tuple, values))
        columns[x, y] = shared.setdefault(surfaces, surfaces)
    return columns


def _coordinate(cell):
    if (
        not isinstance(cell, tuple)
        or len(cell) != 3
        or any(type(value) is not int for value in cell)
        or any(not -(1 << 31) <= value < (1 << 31) for value in cell[:2])
        or not -32768 <= cell[2] < 32768
    ):
        raise ValueError("Invalid native LOS coordinate")


@lru_cache(maxsize=8192)
def static_ray(map_id, source, target):
    """Sf.bfZ/bfX/m against complete original static Vz columns."""
    _coordinate(source)
    _coordinate(target)
    columns = topology_columns(map_id)
    fields = dict(zip(("bnO", "bnP", "bnQ", "bnR", "bnS", "bnT"), source + target))
    probes = set()

    def check():
        x, y = fields["bnU"], fields["bnV"]
        surfaces = columns.get((x, y))
        if not surfaces:
            return False
        # Sf.bfX bypasses VE.h only on source/target XY, not all ray cells.
        if (x, y) not in (source[:2], target[:2]):
            probes.add((x, y))
        low, high = fields["bnW"], fields["bnX"]
        for index, (altitude, height, transparent) in enumerate(surfaces):
            if altitude <= low:
                continue
            if altitude - height >= high:
                return index > 0
            if high > altitude - height and low < altitude and not transparent:
                return False
        return True

    def step(x, y, z):
        if fields["bnU"] == (1 << 31) - 1:
            fields.update(bnU=x, bnV=y, bnW=z, bnX=z)
            return True
        if (x, y) == (fields["bnU"], fields["bnV"]):
            fields["bnW"] = min(z, fields["bnW"])
            fields["bnX"] = max(z, fields["bnX"])
            return True
        if not check():
            return False
        fields.update(bnU=x, bnV=y, bnW=z, bnX=z)
        return True

    program = ray_program()
    local = [0] * 21
    local[0] = fields
    stack = []
    cursor = 0
    binary = {
        "iadd": lambda a, b: _i32(a + b),
        "isub": lambda a, b: _i32(a - b),
        "imul": lambda a, b: _i32(a * b),
        "ishl": lambda a, b: _i32(a << (b & 31)),
        "iushr": lambda a, b: (a & 0xFFFFFFFF) >> (b & 31),
    }
    comparisons = {
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
        "lt": lambda a, b: a < b,
        "le": lambda a, b: a <= b,
        "gt": lambda a, b: a > b,
        "ge": lambda a, b: a >= b,
    }
    for _ in range(2000000):
        instruction = program[cursor]
        op = instruction[0]
        cursor += 1
        if op == "constant":
            stack.append(instruction[1])
        elif op in ("aload", "iload"):
            stack.append(local[instruction[1]])
        elif op == "istore":
            local[instruction[1]] = stack.pop()
        elif op == "getfield":
            stack.append(stack.pop()[instruction[1]])
        elif op == "putfield":
            value = stack.pop()
            stack.pop()[instruction[1]] = value
        elif op in binary:
            b = stack.pop()
            a = stack.pop()
            stack.append(binary[op](a, b))
        elif op == "ineg":
            stack.append(_i32(-stack.pop()))
        elif op == "i2s":
            stack.append(_short(stack.pop()))
        elif op == "iinc":
            local[instruction[1]] = _i32(local[instruction[1]] + instruction[2])
        elif op == "goto":
            cursor = instruction[1]
        elif op.startswith("if_icmp"):
            b = stack.pop()
            a = stack.pop()
            if comparisons[op[7:]](a, b):
                cursor = instruction[1]
        elif op.startswith("if"):
            if comparisons[op[2:]](stack.pop(), 0):
                cursor = instruction[1]
        elif op == "invokevirtual":
            if instruction[1] == "m":
                z, y, x = stack.pop(), stack.pop(), stack.pop()
                stack.pop()
                stack.append(int(step(x, y, z)))
            elif instruction[1] == "bfX":
                stack.pop()
                stack.append(int(check()))
            else:
                raise ValueError("Unaudited native LOS method")
        elif op == "ireturn":
            return bool(stack.pop()), frozenset(probes)
        else:
            raise ValueError("Unaudited native LOS arithmetic opcode")
    raise ValueError("Native LOS ray exceeds bounded runtime work")


def cast_rays(map_id, source, target, *, source_height, target_height):
    """fcr.a: first raised-source/base-target ray, then raised-target ray.

    Heights are actual signed-byte amP.bcK, not invented actor defaults.
    """
    if any(
        type(v) is not int or not -128 <= v < 128
        for v in (source_height, target_height)
    ):
        raise ValueError("Missing authoritative native actor LOS height")
    offset = _short(int(_float32(_float32(source_height) * _float32(0.8))))
    if offset < 0:
        return ((True, frozenset()),)
    raised = tuple(source[:2]) + (_short(source[2] + offset),)
    target_offset = max(6, int(_float32(_float32(target_height) * _float32(0.8))))
    higher = tuple(target[:2]) + (_short(target[2] + target_offset),)
    return (
        static_ray(map_id, raised, tuple(target)),
        static_ray(map_id, raised, higher),
    )
