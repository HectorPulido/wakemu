"""Original eWX fixed-PC assignment and reversal of its measured setter delta.

The requested amount, mutable Qe value and immutable removal delta are distinct.
No state or spell reference participates in dispatch.
"""
from wakfu_server import native_catalog as protocol_catalog
from dataclasses import replace
from functools import lru_cache
import json
from pathlib import Path
from .combat_parameters import parameter_value
from .combat_maximum_resource import _int32
from .combat_stat_handler import StatExecutionContext, _current, _bounds, _write
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value


@lru_cache(maxsize=1)
def set_current_registry():
    return protocol_catalog.load(
        Path(__file__).resolve().parents[2]
        / "protocol"
        / "native-set-current-characteristic.json"
    )["effects"]


def set_current_transition(*, current, requested, minimum, maximum, frozen=False):
    """eWX.g: PA.on then PA.aYS, and Java-int difference of effective values."""
    for value in (current, requested, minimum, maximum):
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Missing native signed characteristic value")
    if (
        type(frozen) is not bool
        or minimum > maximum
        or not minimum <= current <= maximum
    ):
        raise ValueError("Invalid native current characteristic bounds")
    after = current if frozen else max(minimum, min(maximum, requested))
    return after, _int32(after - current)


def remove_set_current_transition(*, current, delta, minimum, maximum, frozen=False):
    return set_current_transition(
        current=current,
        requested=_int32(current - delta),
        minimum=minimum,
        maximum=maximum,
        frozen=frozen,
    )[0]


FAMILIES = frozenset(map(int, set_current_registry()))


class NativeSetCurrentCharacteristicHandler:
    native_runner_value_verified = True

    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        rng,
        event_lifecycle=None
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.rng, self.event_lifecycle = rng, event_lifecycle
        self.prepared, self.runner_amounts = {}, {}

    def _row(self, effect):
        row = set_current_registry().get(str(effect["effect_class"]))
        if row is None or row["runner"] != "eWX" or row["numeric_kind"] != 0:
            raise ValueError("Missing original eWX fixed numeric PC")
        return row

    def _actors_context(self, effect, invocation):
        target = self.fight.actors.get(invocation.target_id)
        caster = self.fight.actors.get(invocation.caster_id)
        if target is None or caster is None or self.fight.phase != "active":
            raise ValueError("Native eWX requires actual registered actors")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eWX guard and timing authority")
        if context.executable:
            from .combat_runner_target_life import verify_runner_target_life

            verify_runner_target_life(self.fight, target, effect, invocation=invocation)
        return caster, target, context

    def _events(self, effect, extra=()):
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Missing native eWX source event masks")
        return tuple(sorted({*self._row(effect)["events"], *(masks[6] or ()), *extra}))

    def _calculate(self, effect, invocation):
        caster, target, context = self._actors_context(effect, invocation)
        stat = self._row(effect)["fixed_stat_id"]
        parameters = effect["parameters"]
        if not isinstance(parameters, (tuple, list)) or len(parameters) % 2:
            raise ValueError("Malformed native eWX parameter pairs")
        value = (
            parameter_value(parameters, 0, invocation.level)
            if parameters
            else _current(caster, stat)
        )
        value = apply_context_value(
            value,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return context, value

    def prepare(self, effect, values, invocation):
        self._row(effect)
        self._actors_context(effect, invocation)
        events = self._events(effect)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        self.runner_amounts[uid] = runner
        try:
            if self.event_lifecycle is not None:
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=0,
                    channel=1,
                    _event_ids=events,
                    runner_modifier=runner,
                )
            self.prepared[uid] = self._calculate(effect, invocation)
            runner.set_calculated(self.prepared[uid][1])
        except BaseException:
            self.runner_amounts.pop(uid, None)
            self.prepared.pop(uid, None)
            raise
        return invocation

    def cancel_prepared(self, invocation):
        uid = invocation.native_running_uid
        if uid is not None:
            self.prepared.pop(uid, None)
            self.runner_amounts.pop(uid, None)

    def __call__(self, effect, values, invocation):
        row = self._row(effect)
        uid = invocation.native_running_uid
        if uid is not None and uid not in self.prepared:
            raise ValueError("Missing prepared native eWX runner")
        context, value = (
            self._calculate(effect, invocation)
            if uid is None
            else self.prepared.pop(uid)
        )
        runner = self.runner_amounts.pop(uid, None)
        if not context.executable:
            return False
        uid = uid or self.allocate_uid()
        if runner is None:
            runner = NativeRunnerAmount(
                uid, effect["effect_class"], rng=self.rng, value=value
            )
        events = self._events(effect)
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=value,
                channel=2,
                _event_ids=events,
                runner_modifier=runner,
            )
        target = self.fight.actors[invocation.target_id]
        stat = row["fixed_stat_id"]
        from .combat_actor_snapshot import native_actor_catalog

        characteristic = native_actor_catalog()["characteristics"][str(stat)]
        # Expandable fff retains an additional raw-current value. That producer
        # must exist before this effective-current-only consumer can support it.
        if characteristic["expandable"] and runner.value > target.effect_maxima.get(
            stat, -1
        ):
            raise ValueError("Native eWX expandable raw current authority required")
        current, (minimum, maximum) = _current(target, stat), _bounds(target, stat)
        after, delta = set_current_transition(
            current=current,
            requested=runner.value,
            minimum=minimum,
            maximum=maximum,
            frozen=stat in target.effect_frozen,
        )
        caster = self.fight.actors[invocation.caster_id]
        caster_before = _current(caster, stat)
        _write(self.fight, invocation.caster_id, target, stat, after)
        caster_change = _int32(_current(caster, stat) - caster_before)
        runner.set_applied(after)
        self.fight._event(
            "characteristic_changed",
            source_id=invocation.caster_id,
            target_id=target.id,
            stat_id=stat,
            actual=delta,
            current=after,
        )
        changed_event = (
            row["gain_event"]
            if caster_change > 0
            else row["loss_event"]
            if caster_change < 0
            else -1
        )
        events = self._events(effect, () if changed_event < 0 else (changed_event,))

        def payload_for(amount):
            return owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=target.id,
                value=amount,
                timing_payload=context.timing_payload,
            )

        payload = payload_for(after)
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=target.id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family="eWX",
                stat_id=stat,
                actual=after,
                setter_delta=delta,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                effect_class=effect["effect_class"],
                target_id=target.id,
                uid=uid,
                running_effect_payload=payload,
            )
        )
        if context.retained and self.event_lifecycle is not None:
            register = getattr(self.event_lifecycle, "register_applied", None)
            if callable(register):
                register(effect, invocation, uid)
        runner.finish_application()
        if self.event_lifecycle is not None:
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=runner.value,
                    channel=channel,
                    _event_ids=events,
                    runner_modifier=runner,
                )
        if context.retained:
            entry = self.fight.owned_stat_effects[uid]
            entry["actual"], entry["payload"] = (
                runner.value,
                payload_for(runner.value).hex(),
            )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_set_current_characteristic(handler, uid):
    from .combat_effect_removal import running_effect_removal

    entry = handler.fight.owned_stat_effects[uid]
    if entry.get("family") != "eWX" or type(entry.get("setter_delta")) is not int:
        raise ValueError("Missing native eWX immutable removal delta")
    target = handler.fight.actors.get(entry["target_id"])
    if target is None:
        raise ValueError("Missing native eWX removal target")
    stat = entry["stat_id"]
    current, (minimum, maximum) = _current(target, stat), _bounds(target, stat)
    from .combat_actor_snapshot import native_actor_catalog

    if (
        native_actor_catalog()["characteristics"][str(stat)]["expandable"]
        and _int32(current - entry["setter_delta"]) > maximum
    ):
        raise ValueError("Native eWX expandable removal raw current authority required")
    after = remove_set_current_transition(
        current=current,
        delta=entry["setter_delta"],
        minimum=minimum,
        maximum=maximum,
        frozen=stat in target.effect_frozen,
    )
    _write(handler.fight, entry["caster_id"], target, stat, after)
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=target.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
