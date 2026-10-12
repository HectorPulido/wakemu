"""Native1100/eYo child level; requires explicit actual fBg instance authority."""
from dataclasses import dataclass
import math
from wakfu_server.combat_parameters import _float32, _integer
from wakfu_server.combat_state_level_group import float_parameter
from wakfu_server.combat_effect_dispatch import UnsupportedEffectExecution


@dataclass(frozen=True)
class InstanceDifficultySnapshot:
    actor_id: int
    difficulty: int | None
    source: str

    def __post_init__(self):
        if type(self.actor_id) is not int:
            raise ValueError("Native instance snapshot requires actual PV identity")
        expected = (
            "fBg.drG.Optional.empty" if self.difficulty is None else "fBg.drG.fBf.GN"
        )
        if self.source != expected or (
            self.difficulty is not None
            and (
                type(self.difficulty) is not int
                or not -(1 << 31) <= self.difficulty < (1 << 31)
            )
        ):
            raise ValueError("Missing exact native instance difficulty producer")


def native_override(effect, values, invocation, resolve_instance):
    if effect["effect_class"] != 1100:
        raise UnsupportedEffectExecution("Unsupported instance-level group")
    parameters = values["parameters"]
    count = effect.get("parameter_count")
    if type(count) is not int or count < 0 or len(parameters) != count or count == 2:
        raise UnsupportedEffectExecution("Unknown native1100 parameter variant")
    identity = (
        invocation.caster_id
        if count == 0 or parameters[0] == 0
        else invocation.target_id
    )
    if identity is None:
        difficulty = 0  # Native null/non-fBg PV branch, not a missing snapshot.
    else:
        if not callable(resolve_instance):
            raise UnsupportedEffectExecution(
                "Missing native1100 actual instance authority"
            )
        snapshot = resolve_instance(identity)
        if (
            not isinstance(snapshot, InstanceDifficultySnapshot)
            or snapshot.actor_id != identity
        ):
            raise UnsupportedEffectExecution(
                "Missing native1100 actual instance snapshot"
            )
        difficulty = 0 if snapshot.difficulty is None else snapshot.difficulty
    base = (
        float_parameter(effect["parameters"], 1, invocation.level)
        if count >= 3
        else 0.0
    )
    factor = (
        float_parameter(effect["parameters"], 2, invocation.level)
        if count >= 3
        else 1.0
    )
    amount = _float32(base + _float32(factor * _float32(difficulty)))
    return int(_integer(math.floor(amount + 0.5) if math.isfinite(amount) else amount))


def runtime_child_level(
    effect, values, invocation, fight, *, return_native_override=False
):
    from .combat_instance_publication import require_current_publication

    try:
        require_current_publication(fight)
    except ValueError as error:
        raise UnsupportedEffectExecution(str(error)) from error
    snapshots = getattr(fight, "native_instance_difficulty_snapshots", None)
    override = native_override(
        effect,
        values,
        invocation,
        snapshots.get if isinstance(snapshots, dict) else None,
    )
    if return_native_override:
        return override
    return invocation.level if override == -1 else ((override + 32768) % 65536) - 32768
