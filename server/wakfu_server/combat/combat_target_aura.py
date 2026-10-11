"""eYJ338's target-PV faN constructor and ij21-only additional data."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NativeTargetAuraConstruction:
    runner_uid: int
    area_uid: int
    target_id: int
    level: int

    def __post_init__(self):
        if (
            any(
                type(uid) is not int or not 0 < uid < 2**63
                for uid in (self.runner_uid, self.area_uid)
            )
            or self.runner_uid == self.area_uid
            or type(self.target_id) is not int
            or self.target_id == 0
            or type(self.level) is not int
            or not -32768 <= self.level <= 32767
        ):
            raise ValueError("Missing actual eYJ constructor identities")


def target_aura_additional(area_uid):
    from .combat_effects import _integer

    if type(area_uid) is not int or not 0 < area_uid < 2**63:
        raise ValueError("Missing native eYJ rGF area identity")
    return _integer(21, area_uid)


def target_aura_application(
    fight_id,
    action_id,
    *,
    invocation,
    constructor,
    value,
    timing_payload,
    owner,
    owner_id
):
    from .combat_retained_runtime import group_payload
    from .combat_stat_effects import owned_effect_application
    from wakfu_server.wire import proto_fields, proto_field

    if (
        not isinstance(constructor, NativeTargetAuraConstruction)
        or constructor.runner_uid != invocation.native_running_uid
        or constructor.target_id != invocation.target_id
        or constructor.level != invocation.level
    ):
        raise ValueError("Native eYJ constructor differs from running context")
    if not isinstance(timing_payload, bytes):
        raise ValueError("Missing native eYJ TimeDatas")
    fields = dict(proto_fields(timing_payload))
    fields[16], fields[40] = (2**64 - 1), 1
    clock = b"".join(proto_field(tag, fields[tag]) for tag in sorted(fields))
    payload = group_payload(
        uid=constructor.runner_uid,
        base_uid=invocation.base_uid,
        generic_effect=invocation.reference,
        caster_id=invocation.caster_id,
        target_id=invocation.target_id,
        cell=invocation.cell,
        container_type=owner["container_type"],
        container_id=owner_id,
        timing_payload=clock,
        context_payload=None
        if invocation.native_context_hex is None
        else bytes.fromhex(invocation.native_context_hex),
        initial_value=value,
    )
    additional = target_aura_additional(constructor.area_uid)
    payload_fields = dict(proto_fields(payload))
    payload_fields[66] = additional
    payload = b"".join(
        proto_field(tag, payload_fields[tag]) for tag in sorted(payload_fields)
    )
    return (
        13497,
        owned_effect_application(
            fight_id,
            action_id,
            effect_class=338,
            target_id=invocation.target_id,
            uid=constructor.runner_uid,
            running_effect_payload=payload,
        ),
    )


class NativeTargetAuraHandler:
    native_runner_value_verified = True

    def __init__(self, area_handler, retention, *, rng):
        self.area_handler, self.retention, self.rng = area_handler, retention, rng
        self.fight = area_handler.fight
        self.event_lifecycle = None
        self.prepared = {}
        area_handler.target_aura_construction = self.constructor
        area_handler.target_aura_applied = retention.register_applied_target_aura

    def constructor(self, invocation):
        entry = self.prepared.get(invocation.native_running_uid)
        if entry is None:
            raise ValueError("Missing prepared original eYJ constructor")
        return entry[1]

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (tuple, list)) or len(masks) != 7:
                raise ValueError("Missing native eYJ event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                runner_modifier=runner,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                _execution_status=-1,
            )

    def prepare(self, effect, values, invocation):
        from dataclasses import replace
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_parameters import parameter_value
        from .combat_value_transfer import apply_context_value

        if effect.get("effect_class") != 338 or invocation.target_id is None:
            raise ValueError("Missing actual target-PV eYJ recipient")
        uid = self.area_handler.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 338, rng=self.rng)
        try:
            self._phase(effect, invocation, runner, 1)
            value = parameter_value(effect["parameters"], 0, invocation.level)
            area_uid = self.area_handler.allocate_area_uid()  # C -> PW.baj.
            runner.set_calculated(
                apply_context_value(
                    value,
                    None
                    if invocation.native_context_hex is None
                    else bytes.fromhex(invocation.native_context_hex),
                )
            )
            self.prepared[uid] = (
                runner,
                NativeTargetAuraConstruction(
                    uid, area_uid, invocation.target_id, invocation.level
                ),
            )
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        entry = self.prepared.get(invocation.native_running_uid)
        if entry is None:
            raise ValueError("Missing prepared native eYJ runner")
        runner, constructor = entry
        try:
            self._phase(effect, invocation, runner, 2)
            # The shared constructor consumes the exact prepared amount; it
            # must not recalculate C or allocate another PW identity.
            selected = dict(values, parameters=[runner.value])
            result = self.area_handler(effect, selected, invocation)
            if not result:
                return False
            runner.finish_application()
            self._phase(effect, invocation, runner, 3)
            self._phase(effect, invocation, runner, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
            return True
        finally:
            self.cancel_prepared(invocation)
