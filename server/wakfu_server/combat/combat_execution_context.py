"""Exact eVt scalar snapshot and ir serializer; source-runner cloning is separate."""
from dataclasses import dataclass, replace


def _integer(field, value):
    # protobuf int32 uses the sign-extended 64-bit varint for negative values.
    value &= (1 << 64) - 1
    payload = bytearray((field << 3,))
    while value > 127:
        payload.append((value & 127) | 128)
        value >>= 7
    payload.append(value)
    return bytes(payload)


@dataclass(frozen=True)
class NativeExecutionContext:
    """Explicit eVt fields, including constructor values often lost in adapters."""

    bypass_probability: bool
    bypass_criteria: bool
    selection: int
    ban: bool
    forced_value: int
    mc: bool
    bb_i: bool
    forced_mode: int

    def __post_init__(self):
        for name in ("bypass_probability", "bypass_criteria", "ban", "mc", "bb_i"):
            if type(getattr(self, name)) is not bool:
                raise ValueError("Native execution-context boolean is unknown")
        for name in ("selection", "forced_value"):
            value = getattr(self, name)
            if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
                raise ValueError("Native execution-context scalar is not signed int32")
        if type(self.forced_mode) is not int or self.forced_mode not in (0, 1, 2):
            raise ValueError("Unknown native eVu/iu forced-value mode")

    def payload(self):
        # Original eVt.fLV writes every field, even explicit false and NONE.
        return b"".join(
            _integer(field, int(value))
            for field, value in (
                (1, self.bypass_probability),
                (2, self.bypass_criteria),
                (4, self.selection),
                (5, self.ban),
                (6, self.forced_value),
                (7, self.mc),
                (8, self.bb_i),
                (9, self.forced_mode),
            )
        )

    def sp(self, value):
        return replace(self, selection=value)

    def mb(self, value):
        return replace(self, ban=value)

    def mark_bb_i(self):
        return replace(self, bb_i=True)

    def set_mc(self, value):
        return replace(self, mc=value)

    def force(self, value, mode):
        if type(mode) is not int or mode not in (1, 2):
            raise ValueError("Native eVt.a cannot force with NONE")
        return replace(self, forced_value=value, forced_mode=mode)


def constructed_execution_context():
    """Original new eVt(), not evidence that a given dispatch uses fresh PS."""
    return NativeExecutionContext(False, False, -1, True, 0, False, False, 0)
