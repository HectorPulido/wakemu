"""Exact eWO HP PA setters, independent of damage/healing or effect dispatch.

The caller owns original Qe guards, chance, parameter evaluation, events and
retention. This primitive never authorizes a family or manufactures raw HP.
"""
from .combat_casting_range import int32
from .combat_hp_raw import (
    hp_raw_current,
    set_hp_raw_minimum,
    set_hp_raw_maximum,
    shift_hp_raw_current,
)
from .combat_maximum_resource import _snapshot


def apply_hp_maximum_reduction(actor, amount, *, definition_type, reduce_current):
    """eWO.fb + fNL: minimum, maximum, then remaining current reduction.

    PK.aZD==2 bypasses the maximum-one guard; this is not a death-prevention
    guard for current HP. A raw HP operand must already have a real producer.
    """
    if (
        type(amount) is not int
        or not -(1 << 31) <= amount < (1 << 31)
        or type(definition_type) is not int
        or definition_type not in (0, 1, 2)
        or type(reduce_current) is not bool
    ):
        raise ValueError("Missing exact native eWO HP application authority")
    current, raw_max, maximum, _, raw_min, *_ = _snapshot(actor, 1)
    hp_raw_current(actor)
    if definition_type != 2:
        difference = int32(maximum - amount)
        if difference <= 0:
            amount = int32(amount + int32(difference - 1))
    if maximum != (1 << 31) - 1:
        if raw_min != -(1 << 31):
            set_hp_raw_minimum(actor, int32(raw_min - amount))
        if raw_max != (1 << 31) - 1:
            set_hp_raw_maximum(actor, int32(raw_max - amount))
    if reduce_current:
        remaining = int32(amount - int32(current - actor.hp))
        shift_hp_raw_current(actor, remaining, subtract=True)
    # ffw.sgC.fZs=4 for nonzero Qe value, fZu=2 for changed current.
    events = (() if amount == 0 else (4,)) + (() if actor.hp == current else (2,))
    return amount, tuple(sorted(events))


def remove_hp_maximum_reduction(actor, amount, *, restore_current):
    """eWO.bbR: maximum, minimum, then optional current restoration."""
    if (
        type(amount) is not int
        or not -(1 << 31) <= amount < (1 << 31)
        or type(restore_current) is not bool
    ):
        raise ValueError("Missing exact native eWO HP removal authority")
    _, raw_max, _, _, raw_min, *_ = _snapshot(actor, 1)
    hp_raw_current(actor)
    if raw_max != (1 << 31) - 1:
        set_hp_raw_maximum(actor, int32(raw_max + amount))
    if raw_min != -(1 << 31):
        set_hp_raw_minimum(actor, int32(raw_min + amount))
    if restore_current:
        shift_hp_raw_current(actor, amount)


from .combat_maximum_resource import (
    NativeMaximumResourceHandler,
    maximum_application_amount,
)
from .combat_stat_handler import StatExecutionContext
from .combat_summon_initialization import registered_or_detached_actor
from .combat_npc_initialization import constructor_stat_context
from .combat_parameters import parameter_value
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_stat_effects import owned_effect_payload, evaluated_effect_delivery
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


class NativeHPMaximumReductionHandler(NativeMaximumResourceHandler):
    """eVi21/eWO PC1, preserving original HP raw setters and Qe phases."""

    native_runner_value_verified = True

    def __init__(self, *args, probability=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.probability = probability

    def _context(self, effect, invocation):
        if (
            effect.get("effect_class") != 21
            or len(effect.get("parameters", ())) not in (2, 4, 6, 8)
            or type(effect.get("native_execution_mode")) is not int
            or effect["native_execution_mode"] not in (0, 1, 2)
        ):
            raise ValueError("Unsupported exact native eWO HP definition")
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        if actor is None or (
            not constructor_stat_context(self.fight, invocation)
            and (
                self.fight.phase != "active"
                or invocation.target_id not in self.fight.actors
                or invocation.caster_id not in self.fight.actors
            )
        ):
            raise ValueError("Invalid native eWO HP actors/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native eWO HP guards")
        _snapshot(actor, 1)
        hp_raw_current(actor)
        return context

    def _events(self, effect, *, applied=()):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native eWO HP target event masks")
        return tuple(sorted({*(applied or (4,)), *(masks[6] or ())}))

    def _calculate(self, effect, invocation):
        context = self._context(effect, invocation)
        parsed = [
            parameter_value(effect["parameters"], i, invocation.level)
            for i in range(len(effect["parameters"]) // 2)
        ]
        amount = parsed[0]
        if amount == -1:
            amount = maximum_application_amount(
                amount, invocation, context_applied=True
            )
        elif amount == -2:
            amount = registered_or_detached_actor(self.fight, invocation.target_id).hp
        from .combat_value_transfer import apply_context_value

        amount = apply_context_value(
            amount,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        restore = len(parsed) < 3 or parsed[2] == 1
        reduce = len(parsed) < 4 or parsed[3] == 1
        return context, amount, restore, reduce

    def _apply(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is None:
            context, amount, restore, reduce = self._calculate(effect, invocation)
        else:
            if uid not in self.prepared_maxima:
                raise ValueError("Missing prepared native eWO HP runner")
            context, amount, restore, reduce = self.prepared_maxima.pop(uid)
        if not context.executable:
            return False
        parameters = effect["parameters"]
        chance = (
            parameter_value(parameters, 1, invocation.level)
            if len(parameters) >= 4
            else 100
        )
        chance = 100 if chance < 0 else max(0, min(100, chance))
        if chance < 100:
            if not callable(self.probability):
                raise ValueError("Missing native eWO HP chance RNG")
            accepted = self.probability(chance, invocation)
            if type(accepted) is not bool:
                raise ValueError("Unknown native eWO HP chance result")
            if not accepted:
                return False
        runner = self.runner_amounts.get(uid)
        if self.event_lifecycle is not None:
            uid = uid or self.allocate_uid()
            runner = runner or NativeRunnerAmount(uid, 21, rng=self.rng, value=amount)
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=amount,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            live = self._context(effect, invocation)
            if not live.executable:
                return False
            if live.retained != context.retained:
                raise ValueError("Native eWO HP retention changed during L2")
            amount = runner.value
        amount = maximum_application_amount(amount, invocation, context_applied=True)
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        before = actor.hp
        amount, events = apply_hp_maximum_reduction(
            actor,
            amount,
            definition_type=effect["native_execution_mode"],
            reduce_current=reduce,
        )
        uid = uid or self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=amount,
            timing_payload=context.timing_payload,
        )
        additional = _integer(34, int(restore)) + _integer(35, int(reduce))
        payload += b"\x42" + _varint(len(additional)) + additional
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=21,
                family="eWO_HP",
                stat_id=1,
                actual=amount,
                restore_current=restore,
                reduce_current=reduce,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.fight._event(
            "characteristic_changed",
            source_id=invocation.caster_id,
            target_id=actor.id,
            stat_id=1,
            actual=int32(actor.hp - before),
            current=actor.hp,
        )
        if runner is not None:
            runner.set_applied(amount)
        if runner is None or not runner.notification_suppressed:
            self.packets.append(
                evaluated_effect_delivery(
                    self.fight.id,
                    self.action_id,
                    retained=context.retained,
                    effect_class=21,
                    target_id=actor.id,
                    uid=uid,
                    running_effect_payload=payload,
                )
            )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        if runner is not None:
            runner.finish_application()
        if self.event_lifecycle is not None:
            # eWO removes its declared event4 when applied value is zero.
            masks = effect["target_masks"]
            event_ids = tuple(sorted({*events, *(masks[6] or ())}))
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=runner.value,
                    channel=channel,
                    _event_ids=event_ids,
                    runner_modifier=runner,
                )
        final = amount if runner is None else runner.value
        if context.retained:
            entry = self.fight.owned_stat_effects[uid]
            entry["actual"] = final
            final_payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=actor.id,
                value=final,
                timing_payload=context.timing_payload,
            )
            entry["payload"] = (
                final_payload + b"\x42" + _varint(len(additional)) + additional
            ).hex()
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, final)
        return True


def remove_owned_hp_maximum_reduction(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = registered_or_detached_actor(handler.fight, entry["target_id"])
    if (
        actor is None
        or entry.get("family") != "eWO_HP"
        or entry.get("effect_class") != 21
    ):
        raise ValueError("Missing actual retained eWO HP actor/owner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=21,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    remove_hp_maximum_reduction(
        actor, entry["actual"], restore_current=entry["restore_current"]
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
