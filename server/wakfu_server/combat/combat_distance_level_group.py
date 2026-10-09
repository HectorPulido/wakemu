"""Native eYi1080/eWd ordered children use distance-derived eVt.SP."""
import math
from dataclasses import replace
from .combat_parameters import _float32, _integer
from .combat_level_group import _native_float_parameter
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_runner_callbacks import notify_runner_value


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def distance_group_amount(effect, level, caster_cell, target_cell):
    if effect.get("effect_class") != 1080 or effect.get("parameter_count") != 1:
        raise ValueError("Native eYi requires one float parameter")
    raw = effect.get("parameters")
    if not isinstance(raw, (tuple, list)) or len(raw) != 2:
        raise ValueError("Missing native eYi raw parameter")
    for cell in (caster_cell, target_cell):
        if (
            not isinstance(cell, (tuple, list))
            or len(cell) != 3
            or any(type(value) is not int for value in cell)
            or any(not -(1 << 31) <= value < (1 << 31) for value in cell[:2])
            or not -32768 <= cell[2] <= 32767
        ):
            raise ValueError("Missing actual native eYi PV/cell coordinates")
    # aBn.A uses int abs/add on XY only; abs(MIN_VALUE) remains MIN_VALUE.
    dx = _i32(abs(_i32(caster_cell[0] - target_cell[0])))
    dy = _i32(abs(_i32(caster_cell[1] - target_cell[1])))
    distance = _i32(dx + dy)
    factor = _native_float_parameter(raw, 0, level)
    amount = _float32(_float32(distance) * factor)
    return int(_integer(math.floor(amount) if math.isfinite(amount) else amount))


class NativeDistanceGroupRunner:
    """Actual L1/C/PS/L2 and post-child L3/L4 for the shared eWd dispatcher."""

    native_runner_value_verified = True

    def __init__(self, *, allocate_uid, actor_position, rng):
        self.allocate_uid, self.actor_position, self.rng = (
            allocate_uid,
            actor_position,
            rng,
        )
        self.event_lifecycle = None
        self.prepared, self.runners = {}, {}

    def __call__(self, effect, values, invocation):
        raise ValueError("Native eWd requires its owned ordered-child dispatcher")

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native eYi event masks")
        return tuple(sorted({0, *(masks[6] or ())}))

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=self._events(effect),
                runner_modifier=runner,
                _nullable_target=True,
            )

    def _calculate(self, effect, invocation):
        amount = distance_group_amount(
            effect,
            invocation.level,
            self.actor_position(invocation.caster_id),
            invocation.cell,
        )
        return apply_context_value(
            amount,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )

    def prepare(self, effect, values, invocation):
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 1080, rng=self.rng)
        self.runners[uid] = runner
        try:
            self._phase(effect, invocation, runner, 1)
            amount = self._calculate(effect, invocation)
            runner.set_calculated(amount)
            self.prepared[uid] = amount
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def start(self, effect, values, invocation, *, event_activation=False):
        uid = invocation.native_running_uid
        if uid is None or (event_activation and uid not in self.prepared):
            # Qe.k event clones run C before L1, unlike fresh preparation.
            uid = uid or self.allocate_uid()
            invocation = replace(invocation, native_running_uid=uid)
            runner = NativeRunnerAmount(
                uid, 1080, rng=self.rng, value=self._calculate(effect, invocation)
            )
            self.runners[uid] = runner
            self.prepared[uid] = runner.value
            self._phase(effect, invocation, runner, 1)
        elif uid not in self.prepared:
            raise ValueError("Missing prepared native eYi runner")
        runner = self.runners[uid]
        self._phase(effect, invocation, runner, 2)
        return invocation, runner.value

    def finish(self, effect, invocation):
        runner = self.runners[invocation.native_running_uid]
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        notify_runner_value(invocation, runner.value)
        self.cancel_prepared(invocation)

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)
