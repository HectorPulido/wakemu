"""eXf667: literal native frN BitSet start/end suppression and retained removal."""
from .combat_effects import _integer, _varint


def suppression_flags(parameters):
    """eXf.C changes defaults only for exactly one evaluated logical parameter."""
    if not isinstance(parameters, (list, tuple)) or any(
        type(v) is not int for v in parameters
    ):
        raise ValueError("Missing native evaluated eXf parameters")
    mode = parameters[0] if len(parameters) == 1 else 0
    return mode != 2, mode != 1


def suppression_payload(start, end):
    if type(start) is not bool or type(end) is not bool:
        raise ValueError("Missing native eXf flags")
    # eXf.b -> iP.a(ij); iN field8, ij.Mc/Me fields17/18.
    nested = _integer(17, int(start)) + _integer(18, int(end))
    return b"\x42" + _varint(len(nested)) + nested


def suppression_bits(actor):
    bits = getattr(actor, "native_turn_suppression_bits", None)
    if type(bits) is not int or bits < 0:
        raise ValueError("Missing actual native eGj.frN BitSet")
    return bits


def mutate_suppression(actor, start, end, *, remove=False):
    if any(type(value) is not bool for value in (start, end, remove)):
        raise ValueError("Missing native eXf mutation flags")
    mask = (2 if start else 0) | (4 if end else 0)
    bits = suppression_bits(actor)
    # bbR literally clears bits. It does not count overlapping retained effects.
    actor.native_turn_suppression_bits = bits & ~mask if remove else bits | mask


def turn_phase_suppressed(actor, phase):
    if phase not in ("start", "end"):
        raise ValueError("Unknown native turn phase")
    return bool(suppression_bits(actor) & (2 if phase == "start" else 4))


class NativeTurnSuppressionHandler:
    def __init__(
        self, fight, packets, *, allocate_uid, action_id, context, authority, rng
    ):
        self.fight, self.packets = fight, packets
        self.allocate_uid, self.action_id = allocate_uid, action_id
        self.context, self.authority, self.rng = context, authority, rng
        self.event_lifecycle = None

    def __call__(self, effect, values, invocation):
        from .combat_carry_handler import NativeCarryHandler
        from .combat_stat_handler import StatExecutionContext
        from .combat_summon_initialization import (
            registered_or_detached_actor,
            detached_actor,
        )
        from .combat_global_pv_collections import global_fighter_registered
        from .combat_parameters import parameter_value
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_ai_control import ai_control_delivery
        from .combat_runner_callbacks import notify_runner_value

        if effect.get("effect_class") != 667:
            raise ValueError("Wrong native eXf runner")
        NativeCarryHandler.require_execution_context(invocation)
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Missing native eXf execution authority")
        if not ctx.executable:
            return False
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        eligible = False
        if actor is not None:
            metadata = self.authority(self.fight, actor)
            if metadata.targeting.get("is_eGj") is True:
                # big.dnz: absent fight in the actual detached constructor is false.
                eligible = detached_actor(
                    self.fight, actor.id
                ) is None and global_fighter_registered(self.fight, actor.id)
        parameters = effect.get("parameters")
        if not isinstance(parameters, (list, tuple)) or len(parameters) % 2:
            raise ValueError("Missing native eXf logical parameters")
        if eligible:
            suppression_bits(actor)  # Validate before allocating or observing.
        uid = self.allocate_uid()
        runner = NativeRunnerAmount(uid, 667, rng=self.rng)

        def phase(channel):
            if self.event_lifecycle is not None:
                masks = effect.get("target_masks")
                if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                    raise ValueError("Missing native eXf event masks")
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=0,
                    channel=channel,
                    runner_modifier=runner,
                    _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                    _execution_status=-1,
                )

        phase(1)
        # C runs after L1: a callback may have changed participation or PCs.
        if eligible:
            eligible = global_fighter_registered(self.fight, actor.id)
        flags = suppression_flags(
            [parameter_value(parameters, 0, invocation.level)]
            if eligible and len(parameters) == 2
            else []
        )
        phase(2)
        packet, payload = ai_control_delivery(
            self.fight.id,
            self.action_id,
            effect,
            invocation,
            uid=uid,
            value=0,
            timing_payload=ctx.timing_payload,
        )
        extra = suppression_payload(*flags)
        payload += extra
        from .combat_stat_effects import owned_effect_delivery

        packet = owned_effect_delivery(
            self.fight.id,
            self.action_id,
            native_opcode=12613,
            effect_class=667,
            target_id=invocation.target_id,
            uid=uid,
            running_effect_payload=payload,
        )
        if eligible:
            mutate_suppression(actor, *flags)
        if ctx.retained:
            if actor is None:
                raise ValueError("Missing retained native eXf manager")
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=667,
                family="eXf",
                target_id=actor.id,
                caster_id=invocation.caster_id,
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
                native_suppression_start=flags[0],
                native_suppression_end=flags[1],
                native_suppression_applied=eligible,
            )
        self.packets.append(packet)
        if ctx.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        runner.finish_application()
        phase(3)
        phase(4)
        notify_runner_value(invocation, 0)
        return True


def remove_turn_suppression(handler, uid):
    from .combat_force_characteristic import remove_forced_characteristic

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != "eXf" or row.get("effect_class") != 667:
        raise ValueError("Not a native retained eXf runner")
    actor = handler.fight.actors.get(row["target_id"])
    if row.get("native_suppression_applied") is True:
        if actor is None:
            raise ValueError("Missing native eXf retained target")
        mutate_suppression(
            actor,
            row["native_suppression_start"],
            row["native_suppression_end"],
            remove=True,
        )
    return remove_forced_characteristic(handler, uid)
