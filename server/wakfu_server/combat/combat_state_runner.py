"""Live eWu pending-short controller; Qe.amount remains independent."""
from .combat_trigger_value_modifier import NativeRunnerAmount, _int, _round
from .combat_parameters import _float32


def _short(value):
    return (value + 32768) % 65536 - 32768


class NativeRunnerStateLevel(NativeRunnerAmount):
    def __init__(self, uid, family=304, *, rng, reference=0, level=0, value=0):
        super().__init__(uid, family, rng=rng, value=value)
        if self.owner != "eWu":
            raise ValueError("Native state controller requires original eWu owner")
        self.seed(reference, level)

    def seed(self, reference, level):
        if type(reference) is not int or type(level) is not int:
            raise ValueError("Native eWu reference/level requires integers")
        self.reference = _short(reference)
        self.pending_level = self.seed_level = _short(level)
        self.packed = (self.reference << 16) + (self.pending_level & 65535)

    def mutate(self, mode, value, replace):
        if type(mode) is not int or type(value) is not int or type(replace) is not bool:
            raise ValueError("Invalid native eWu modification")
        if mode == 4:
            amount = _float32(value)
            result = _int(
                amount if replace else _float32(_float32(self.pending_level) + amount)
            )
        elif mode == 7:
            ratio = _float32(
                _float32(_float32(self.pending_level) * _float32(value)) / 100
            )
            amount = _round(ratio, self.rng)
            result = amount if replace else self.pending_level + amount
        else:
            return
        self.seed(self.reference, _short(result))
