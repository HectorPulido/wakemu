"""Native eYH325 scalar computation and eGj.lx/dpR control mutation."""
from dataclasses import replace

from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount


def native_ai_control_value(parameter):
    if type(parameter) is not int or not -(1 << 31) <= parameter < (1 << 31):
        raise ValueError("Missing native evaluated eYH parameter")
    return int(parameter > 0)


def set_native_ai_control(actor, enabled):
    """eGj.lx delegates to eGZ.lx; preserve the existing typed pHH producer."""
    if type(enabled) is not bool:
        raise ValueError("Unknown native AI-control mutation")
    if type(getattr(actor, "native_controlled_by_ai", None)) is not bool:
        raise ValueError("Missing actual native eGZ control field")
    actor.native_controlled_by_ai = enabled


def restore_native_ai_control(actor, authority):
    """eYH.bbR restores dpR, not the value preceding this effect."""
    baseline = getattr(authority, "native_ai_control_baseline", None)
    if type(baseline) is not bool:
        raise ValueError("Missing actual native dpR baseline authority")
    set_native_ai_control(actor, baseline)


class NativeAIControlHandler:
    """General eYH runner with explicit source-authoritative wire delivery."""

    def __init__(
        self, fight, packets, *, allocate_uid, context, authority, rng, delivery
    ):
        self.fight, self.packets = fight, packets
        self.allocate_uid, self.context, self.authority = (
            allocate_uid,
            context,
            authority,
        )
        self.rng, self.delivery = rng, delivery
        self.event_lifecycle = None
        self.runners = {}

    def _context(self, effect, invocation):
        if effect.get("effect_class") != 325:
            raise ValueError("Wrong native AI-control runner")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native AI-control execution authority")
        if invocation.native_context_hex is None:
            raise ValueError("Missing actual native eYH execution-context origin")
        from .combat_effect_removal import _identity_fields

        fields = _identity_fields(
            bytes.fromhex(invocation.native_context_hex),
            integer_fields=(1, 2, 4, 5, 6, 7, 8, 9),
        )
        if (
            set(fields) != {1, 2, 4, 5, 6, 7, 8, 9}
            or any(fields[k] not in (0, 1) for k in (1, 2, 5, 7, 8))
            or fields[9] not in (0, 1, 2)
        ):
            raise ValueError("Missing complete actual native eVt execution context")
        return context

    def _phase(self, effect, invocation, uid, channel):
        if self.event_lifecycle is None:
            return
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7:
            raise ValueError("Missing native AI-control event masks")
        runner = self.runners[uid]
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(sorted({0, *(masks[6] or ())})),
            _execution_status=-1,
        )

    def cancel_prepared(self, invocation):
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, 325, rng=self.rng)
            self.runners[uid] = runner
            self._phase(effect, invocation, uid, 1)
            runner.value = native_ai_control_value(
                parameter_value(effect["parameters"], 0, invocation.level)
            )
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        fresh = invocation.native_running_uid is None
        if fresh:
            invocation = self.prepare(effect, values, invocation)
        uid = invocation.native_running_uid
        if uid not in self.runners:
            raise ValueError("Missing actual prepared native AI-control runner")
        try:
            context = self._context(effect, invocation)
            if not context.executable:
                return False
            self._phase(effect, invocation, uid, 2)
            runner = self.runners[uid]
            target = self.fight.actors.get(invocation.target_id)
            if target is not None:
                authority = self.authority(self.fight, target)
                if authority.targeting.get("is_eGj") is True:
                    if (
                        type(getattr(target, "native_controlled_by_ai", None))
                        is not bool
                    ):
                        raise ValueError("Missing actual native eGZ control field")
                else:
                    target = None
            baseline = None
            if context.retained:
                if target is None:
                    raise ValueError("Missing retained native AI-control fighter")
                baseline = getattr(authority, "native_ai_control_baseline", None)
                if type(baseline) is not bool:
                    raise ValueError("Missing actual native dpR baseline authority")
            packet, payload = self.delivery(
                effect,
                invocation,
                uid=uid,
                value=runner.value,
                timing_payload=context.timing_payload,
            )
            if (
                not isinstance(packet, tuple)
                or len(packet) != 2
                or type(packet[0]) is not int
                or not isinstance(packet[1], bytes)
            ):
                raise ValueError("Missing actual native AI-control delivery")
            if target is not None:
                set_native_ai_control(target, runner.value == 1)
            if context.retained:
                self.fight.owned_stat_effects[uid] = dict(
                    uid=uid,
                    effect_class=325,
                    family="eYH",
                    caster_id=invocation.caster_id,
                    target_id=target.id,
                    actual=0,
                    stat_id=None,
                    payload=payload.hex(),
                    state_uid=invocation.state_uid,
                    timer=None if context.timer is None else dict(vars(context.timer)),
                    native_ai_control_baseline=baseline,
                )
            self.packets.append(packet)
            if context.retained and self.event_lifecycle is not None:
                # Actual Qe/PT insertion precedes L3/L4, whose complete view
                # must include this just-applied retained runner.
                self.event_lifecycle.register_applied(effect, invocation, uid)
            runner.finish_application()
            self._phase(effect, invocation, uid, 3)
            self._phase(effect, invocation, uid, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
            return True
        finally:
            self.cancel_prepared(invocation)


def ai_control_delivery(
    fight_id, action_id, effect, invocation, *, uid, value, timing_payload
):
    from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
    from .combat_displacement import position_payload
    from .combat_effects import _varint

    payload = owned_effect_payload(
        uid=uid,
        base_uid=invocation.base_uid,
        generic_effect=invocation.reference,
        caster_id=invocation.caster_id,
        target_id=invocation.target_id,
        value=value,
        timing_payload=timing_payload,
        execution_status=-1,
        executed=True,
    )
    position = position_payload(invocation.cell)
    context = bytes.fromhex(invocation.native_context_hex)
    payload += b"\x2a" + _varint(len(position)) + position
    payload += b"\x6a" + _varint(len(context)) + context
    packet = owned_effect_delivery(
        fight_id,
        action_id,
        native_opcode=12613,
        effect_class=325,
        target_id=invocation.target_id,
        uid=uid,
        running_effect_payload=payload,
    )
    return packet, payload


def remove_ai_control(handler, uid):
    from types import SimpleNamespace
    from .combat_effect_removal import running_effect_removal

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != "eYH" or row.get("effect_class") != 325:
        raise ValueError("Not a native retained AI-control runner")
    actor = handler.fight.actors[row["target_id"]]
    baseline = row.get("native_ai_control_baseline")
    if type(baseline) is not bool:
        raise ValueError("Missing actual native dpR retained baseline")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=325,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    restore_native_ai_control(
        actor, SimpleNamespace(native_ai_control_baseline=baseline)
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
