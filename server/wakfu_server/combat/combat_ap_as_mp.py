"""Native eWq808 installs an actual AP PA observer and links AP deltas to MP."""
from dataclasses import replace
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_effect_removal import running_effect_removal


class NativeAPAsMPHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, authority
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng, self.authority = context, rng, authority
        self.event_lifecycle, self.prepared = None, {}

    def _context(self, effect, invocation):
        if (
            effect["effect_class"] != 808
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
            or invocation.target_id not in self.fight.actors
        ):
            raise ValueError("Native eWq requires actual fighters")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eWq execution authority")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eWq event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
            )

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 808, rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        from .combat_maximum_resource import _snapshot

        actor = self.fight.actors[invocation.target_id]
        _, _, amount, *_ = _snapshot(actor, 2)
        _snapshot(actor, 3)
        runner.set_calculated(
            apply_context_value(
                amount,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared[uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        context = self._context(effect, invocation)
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.pop(invocation.native_running_uid, None)
        if runner is None:
            raise ValueError("Missing prepared native eWq runner")
        if not context.executable:
            return False
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable:
            return False
        actor = self.fight.actors[invocation.target_id]
        if not context.retained:
            raise ValueError("Native eWq unretained listener ownership unsupported")
        from .combat_maximum_resource import (
            _snapshot,
            _write,
            effective_maximum,
            _int32,
        )
        from .combat_resource_pa_notifications import (
            attach_ap_listener,
            set_resource_maximum,
            shift_resource_current,
        )
        from .combat_property_stack import add_property

        counts = self.authority.property_counts(self.fight, actor)
        ap, *_ = _snapshot(actor, 2)
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, 3
        )
        set_resource_maximum(self.fight, actor, 3, _int32(raw + runner.value))
        shift_resource_current(self.fight, actor, 3, ap)
        attach_ap_listener(self.fight, actor, runner.uid)
        add_property(counts, 50)
        actor.native_fight_property_counts = counts
        actor.native_fight_properties = frozenset(
            k for k, v in counts.items() if v != 0
        )

        def payload_for(value):
            return owned_effect_payload(
                uid=runner.uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=actor.id,
                value=value,
                timing_payload=context.timing_payload,
            )

        payload = payload_for(runner.value)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=808,
                family="eWq",
                stat_id=None,
                actual=runner.value,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                effect_class=808,
                target_id=actor.id,
                uid=runner.uid,
                running_effect_payload=payload,
            )
        )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, runner.uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        if context.retained:
            row = self.fight.owned_stat_effects[runner.uid]
            row["actual"], row["payload"] = (
                runner.value,
                payload_for(runner.value).hex(),
            )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_ap_as_mp(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row["family"] != "eWq":
        raise ValueError("Not an owned native AP-as-MP effect")
    actor = handler.fight.actors[row["target_id"]]
    from .combat_maximum_resource import _snapshot, _write, effective_maximum, _int32
    from .combat_resource_pa_notifications import (
        detach_ap_listener,
        set_resource_maximum,
        set_resource_current,
    )
    from .combat_property_stack import remove_property

    counts = getattr(actor, "native_fight_property_counts", None)
    if not isinstance(counts, dict):
        raise ValueError("Missing actual eWq property counters")
    current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(actor, 3)
    accumulated = detach_ap_listener(handler.fight, actor, uid)
    set_resource_maximum(
        handler.fight, actor, 3, _int32(raw - row["actual"] - accumulated)
    )
    set_resource_current(handler.fight, actor, 3, actor.effect_maxima[3])
    remove_property(counts, 50)
    actor.native_fight_properties = frozenset(k for k, v in counts.items() if v != 0)
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=808,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
