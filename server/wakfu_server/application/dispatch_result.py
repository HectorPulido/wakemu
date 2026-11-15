"""Whether a native route preserves or skips the common checkpoint barrier."""

from enum import Enum, auto


class DispatchResult(Enum):
    FALLTHROUGH = auto()
    CONTINUE = auto()
