"""Private immutable LOS publications; proof is loader-owned, never structural.

Only the native source loader calls the private publication functions. A
MappingProxyType alone is insufficient: its backing dictionary may be aliased.
Tokens certify this generation's static advisory inputs, not native QI masks.
"""
from collections import OrderedDict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from threading import RLock
import weakref

_COLUMNS = OrderedDict()
_PROGRAM = None
_GENERATIONS = OrderedDict()
_AUTHORITY = object()
_LOCK = RLock()
_LIMIT = 8
_FIELDS = frozenset("bn" + value for value in "OPQRSTUVWX")


class _SealedColumns(Mapping):
    """Weak-referenceable immutable owner without exposing its private dict."""

    __slots__ = ("__proxy", "__weakref__")

    def __init__(self, authority, columns):
        if authority is not _AUTHORITY:
            raise TypeError("Only the native LOS loader owns sealed columns")
        object.__setattr__(self, "_SealedColumns__proxy", MappingProxyType(columns))

    def __setattr__(self, name, value):
        raise AttributeError("Sealed native LOS columns are immutable")

    def __delattr__(self, name):
        raise AttributeError("Sealed native LOS columns are immutable")

    def __getitem__(self, key):
        return self.__proxy[key]

    def __iter__(self):
        return iter(self.__proxy)

    def __len__(self):
        return len(self.__proxy)

    def get(self, key, default=None):
        return self.__proxy.get(key, default)

    def items(self):
        return self.__proxy.items()

    def keys(self):
        return self.__proxy.keys()

    def values(self):
        return self.__proxy.values()


def _retired_columns(identity, reference):
    with _LOCK:
        record = _COLUMNS.get(identity)
        if record is not None and record[0] is reference:
            del _COLUMNS[identity]


def _digest(value):
    return (
        type(value) is str
        and len(value) == 64
        and all(char in "0123456789abcdef" for char in value)
    )


def _integer(value):
    return type(value) is int and -(1 << 31) <= value < (1 << 31)


def _columns_valid(columns):
    """Inspect shared surface tuples once while preserving order and aliases."""
    if type(columns) is not dict:
        return False
    validated = {}
    for key, surfaces in columns.items():
        if (
            type(key) is not tuple
            or len(key) != 2
            or not all(_integer(value) for value in key)
            or type(surfaces) is not tuple
        ):
            return False
        if id(surfaces) in validated:
            continue
        validated[id(surfaces)] = surfaces
        for surface in surfaces:
            if (
                type(surface) is not tuple
                or len(surface) != 3
                or not _integer(surface[0])
                or not _integer(surface[1])
                or type(surface[2]) is not bool
            ):
                return False
    return True


def _program_valid(program):
    if type(program) is not tuple or not program:
        return False
    unary = {"ineg", "i2s", "ireturn"}
    binary = {"iadd", "isub", "imul", "ishl", "iushr"}
    branches = {"if" + suffix for suffix in ("eq", "ne", "lt", "le", "gt", "ge")}
    branches |= {"if_icmp" + suffix for suffix in ("eq", "ne", "lt", "le", "gt", "ge")}
    for row in program:
        if type(row) is not tuple or not row or type(row[0]) is not str:
            return False
        op = row[0]
        if op in unary | binary:
            valid = len(row) == 1
        elif op == "constant":
            valid = len(row) == 2 and _integer(row[1])
        elif op in {"aload", "iload", "istore"}:
            valid = len(row) == 2 and type(row[1]) is int and 0 <= row[1] < 21
        elif op == "iinc":
            valid = (
                len(row) == 3
                and type(row[1]) is int
                and 0 <= row[1] < 21
                and _integer(row[2])
            )
        elif op in {"getfield", "putfield"}:
            valid = len(row) == 2 and type(row[1]) is str and row[1] in _FIELDS
        elif op == "invokevirtual":
            valid = len(row) == 2 and type(row[1]) is str and row[1] in {"m", "bfX"}
        elif op == "goto" or op in branches:
            valid = len(row) == 2 and type(row[1]) is int and 0 <= row[1] < len(program)
        else:
            valid = False
        if not valid:
            return False
    return True


def _publish_owned_columns(columns, *, map_id, release, source_sha):
    """Transfer a fresh private dict; caller must retain no mutable alias."""
    if (
        type(map_id) is not int
        or map_id <= 0
        or not _digest(release)
        or not _digest(source_sha)
        or not _columns_valid(columns)
    ):
        return None
    projection = _SealedColumns(_AUTHORITY, columns)
    identity = id(projection)
    reference = weakref.ref(projection, lambda ref: _retired_columns(identity, ref))
    with _LOCK:
        _COLUMNS[identity] = (reference, map_id, release, source_sha, object())
        _COLUMNS.move_to_end(id(projection))
        while len(_COLUMNS) > _LIMIT:
            _COLUMNS.popitem(last=False)
    return projection


def _publish_owned_program(program, *, release, source_sha):
    global _PROGRAM
    if not _digest(release) or not _digest(source_sha) or not _program_valid(program):
        return False
    with _LOCK:
        _PROGRAM = (program, release, source_sha, object())
    return True


@dataclass(frozen=True, slots=True, eq=False, init=False)
class _SealedGeneration:
    map_id: int
    release: str
    topology_sha: str
    ray_program_sha: str

    def __init__(self, authority, map_id, release, topology_sha, ray_program_sha):
        if authority is not _AUTHORITY:
            raise TypeError("Only the native LOS publication owner creates generations")
        for key, value in (
            ("map_id", map_id),
            ("release", release),
            ("topology_sha", topology_sha),
            ("ray_program_sha", ray_program_sha),
        ):
            object.__setattr__(self, key, value)

    def __copy__(self):
        return self

    def __deepcopy__(self, memo):
        return self


def _generation(map_id, release, columns, program):
    with _LOCK:
        record = _COLUMNS.get(id(columns))
        if (
            record is None
            or record[0]() is not columns
            or record[1:3] != (map_id, release)
            or _PROGRAM is None
            or _PROGRAM[0] is not program
            or _PROGRAM[1] != release
        ):
            return None
        _COLUMNS.move_to_end(id(columns))
        key = (record[4], _PROGRAM[3], map_id, release)
        previous = _GENERATIONS.get(key)
        if previous is not None:
            _GENERATIONS.move_to_end(key)
            return previous
        token = _SealedGeneration(_AUTHORITY, map_id, release, record[3], _PROGRAM[2])
        _GENERATIONS[key] = token
        while len(_GENERATIONS) > _LIMIT:
            _GENERATIONS.popitem(last=False)
        return token
