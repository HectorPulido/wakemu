"""Native eZR.bbj listener budget, including eVn.cyc level scaling."""

import math
import struct


def _float32(value):
    try:
        return struct.unpack(">f", struct.pack(">f", value))[0]
    except OverflowError:
        return math.copysign(math.inf, value)


def native_execution_count(base, per_level, level):
    """Evaluate Java i2f/fmul/fadd/f2i in original instruction order."""
    if type(base) is not int or not -32768 <= base <= 32767:
        raise ValueError("Native execution-count base requires signed short")
    if type(level) is not int or not -32768 <= level <= 32767:
        raise ValueError("Native execution-count level requires signed short")
    if base < 0:
        return -1
    if isinstance(per_level, bool) or not isinstance(per_level, (int, float)):
        raise ValueError("Missing native execution-count level coefficient")
    value = _float32(_float32(base) + _float32(_float32(level) * _float32(per_level)))
    if math.isnan(value):
        return 0
    if value >= 2147483647:
        return 2147483647
    if value <= -2147483648:
        return -2147483648
    return int(value)
