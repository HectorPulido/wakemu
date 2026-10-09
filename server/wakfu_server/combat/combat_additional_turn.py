"""Exact eWl/SQ/Tc current-cycle insertion; turn delivery remains caller-owned."""


def timeline_round(fight):
    value = getattr(fight, "native_timeline_round", None)
    if type(value) is not int or value <= 0:
        raise ValueError("Missing actual native timeline round")
    return value


def additional_turn_insertion(
    order, current_index, *, mode, offset, caster_id, target_id
):
    if (
        not isinstance(order, (list, tuple))
        or not order
        or any(type(identity) is not int for identity in order)
        or type(current_index) is not int
        or not 0 <= current_index < len(order)
        or any(type(value) is not int for value in (mode, offset, caster_id, target_id))
        or not -(1 << 31) <= mode < 1 << 31
        or not -(1 << 31) <= offset < 1 << 31
    ):
        raise ValueError("Missing actual native current-cycle timeline")
    # SR.pv maps0=current,1=beginning, EVERY other integer=caster.
    base = (
        current_index
        if mode == 0
        else 0
        if mode == 1
        else (order.index(caster_id) if caster_id in order else -1)
    )
    raw = (base + offset + (1 << 31)) % (1 << 32) - (1 << 31)
    if raw <= current_index:
        return dict(
            applied=False,
            reason="eWl-position-not-after-current",
            raw_position=raw,
            insertion=None,
            order=list(order),
            current_index=current_index,
        )
    insertion = raw % (len(order) + 1)  # Actual Tc.a uses Math.floorMod.
    if insertion <= current_index:
        return dict(
            applied=False,
            reason="Tc-slot-not-after-current",
            raw_position=raw,
            insertion=insertion,
            order=list(order),
            current_index=current_index,
        )
    result = list(order)
    result.insert(insertion, target_id)
    return dict(
        applied=True,
        reason=None,
        raw_position=raw,
        insertion=insertion,
        order=result,
        current_index=current_index,
    )


class NativeAdditionalTurnHandler:
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

        if effect.get("effect_class") != 666:
            raise ValueError("Wrong native eWl runner")
        NativeCarryHandler.require_execution_context(invocation)
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Missing native eWl execution authority")
        if not ctx.executable:
            return False
        uid = self.allocate_uid()
        runner = NativeRunnerAmount(uid, 666, rng=self.rng)

        def phase(channel):
            if self.event_lifecycle is not None:
                masks = effect.get("target_masks")
                if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                    raise ValueError("Missing native eWl event masks")
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
        phase(2)
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        if (
            actor is not None
            and detached_actor(self.fight, actor.id) is None
            and self.authority(self.fight, actor).targeting.get("is_eGj") is True
            and global_fighter_registered(self.fight, actor.id)
        ):
            state = self.fight.native_global_pv_collections
            if state["mode"] != "rRn":
                if (
                    self.fight.phase != "active"
                    or self.fight.native_timeline_policy != "feq"
                    or type(self.fight.native_timeline_round) is not int
                    or self.fight.native_timeline_round <= 0
                ):
                    raise ValueError("Missing native eWl current timeline authority")
                result = additional_turn_insertion(
                    self.fight.order,
                    self.fight.turn_index,
                    mode=parameter_value(effect["parameters"], 0, invocation.level),
                    offset=parameter_value(effect["parameters"], 1, invocation.level),
                    caster_id=invocation.caster_id or 0,
                    target_id=actor.id,
                )
                if result["applied"]:
                    if self.fight.native_base_turn_order is None:
                        self.fight.native_base_turn_order = list(self.fight.order)
                    self.fight.order = result["order"]
        packet, payload = ai_control_delivery(
            self.fight.id,
            self.action_id,
            effect,
            invocation,
            uid=uid,
            value=0,
            timing_payload=ctx.timing_payload,
        )
        if ctx.retained:
            if actor is None:
                raise ValueError("Missing retained native eWl manager")
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=666,
                family="eWl",
                target_id=actor.id,
                caster_id=invocation.caster_id,
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        self.packets.append(packet)
        if ctx.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        runner.finish_application()
        phase(3)
        phase(4)
        notify_runner_value(invocation, 0)
        return True


def remove_additional_turn(handler, uid):
    # eWl inherits Qe.bbR's no-op: an applied current-cycle turn is not reversed.
    from .combat_force_characteristic import remove_forced_characteristic

    return remove_forced_characteristic(handler, uid)
