"""Native eWN resource maxima31/AP,41/MP,191/WP, with reversible owned data.

eWN.C parameters: amount, applyCurrent, removeCurrent. eWN.c changes raw
PA.aYV maximum, measures effective maximum delta, then optionally applies it
to current. Flag17 bypasses PC.aZt cap (AP16/MP8; WP cap-1=none).
AdditionalDatas31/32 store booleans;10 stores effective maximum delta.
Raw/effective maxima and percentages follow fff.aYU with Java int overflow
and division truncation; raw PA minima must be explicit, never inferred.
"""
from wakfu_server import native_catalog as protocol_catalog
from .combat_parameters import parameter_value
from .combat_actor_snapshot import native_actor_catalog
from .combat_stat_handler import StatExecutionContext
from .combat_summon_initialization import registered_or_detached_actor
from .combat_npc_initialization import constructor_stat_context
from .combat_stat_effects import (
    owned_effect_payload,
    owned_effect_application,
    evaluated_effect_delivery,
)
from dataclasses import replace
from functools import lru_cache
import json
from wakfu_server.paths import DATA_ROOT
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal
from .combat_observation_delivery import evaluated_application_from_observation

FAMILIES = {20: (1, None), 31: (2, 16), 41: (3, 8), 191: (4, None), 991: (14, None)}


def _int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def effective_maximum(raw, percent, low, high):
    product = _int32(raw * percent)
    quotient = (abs(product) // 100) * (-1 if product < 0 else 1)
    return max(low, min(high, _int32(raw + quotient)))


def _snapshot(actor, stat):
    for name in (
        "effect_stats",
        "effect_maxima",
        "effect_minima",
        "effect_base_maxima",
        "effect_base_minima",
        "effect_percentages",
    ):
        data = getattr(actor, name, None)
        if not isinstance(data, dict) or type(data.get(stat)) is not int:
            raise ValueError("Missing native raw/effective maximum resource snapshot")
    row = native_actor_catalog()["characteristics"][str(stat)]
    low, high = row["hard_minimum"], row["hard_maximum"]
    raw, percent, raw_min = (
        actor.effect_base_maxima[stat],
        actor.effect_percentages[stat],
        actor.effect_base_minima[stat],
    )
    maximum = effective_maximum(raw, percent, low, high)
    minimum = max(low, min(high, raw_min))
    if (
        actor.effect_maxima[stat] != maximum
        or actor.effect_minima[stat] != minimum
        or raw < raw_min
    ):
        raise ValueError("Raw/effective native resource snapshot mismatch")
    if actor.effect_frozen is None:
        raise ValueError("Missing native resource mutability")
    from .combat_hp_raw import hp_raw_present, hp_raw_current

    if stat == 1 and hp_raw_present(actor):
        hp_raw_current(actor)
    elif stat == 14 and getattr(actor, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import copied_raw_current

        copied_raw_current(actor, stat)
    elif stat in actor.effect_frozen or (
        stat in (2, 3)
        and getattr(actor, "effect_resource_raw_currents", None) is not None
    ):
        from .combat_resource_pa_notifications import resource_raw_current

        raw_current = resource_raw_current(actor, stat)
        if actor.effect_stats[stat] != max(minimum, min(maximum, raw_current)):
            raise ValueError("PA raw/effective current snapshot mismatch")
    if stat in (1, 2, 3):
        if (
            getattr(actor, {1: "hp", 2: "ap", 3: "mp"}[stat])
            != actor.effect_stats[stat]
            or getattr(actor, {1: "max_hp", 2: "max_ap", 3: "max_mp"}[stat]) != maximum
        ):
            raise ValueError("Native resource bounds disagree with actor")
    return actor.effect_stats[stat], raw, maximum, minimum, raw_min, percent, low, high


def _write(actor, stat, current, raw, maximum):
    actor.effect_stats[stat] = current
    actor.effect_maxima[stat] = maximum
    actor.effect_base_maxima[stat] = raw
    from .combat_hupper_resource_binding import maximum_changed

    maximum_changed(actor, stat)
    if stat in (1, 2, 3):
        setattr(actor, {1: "hp", 2: "ap", 3: "mp"}[stat], current)
        setattr(actor, {1: "max_hp", 2: "max_ap", 3: "max_mp"}[stat], maximum)


def maximum_application_amount(calculated, invocation, *, context_applied=False):
    """eZR context precedes eWN.c's conditional actual-Qe -1 substitution."""
    from .combat_value_transfer import apply_context_value
    from .combat_event_replay import NativeEventSource
    from .combat_final_modifier import triggering_runner_source
    from .combat_trigger_value_modifier import NativeRunnerAmount

    if calculated == -2 and not context_applied:
        calculated = maximum_calculated_amount(calculated, invocation)
    amount = (
        calculated
        if context_applied
        else apply_context_value(
            calculated,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
    )
    if amount != -1 or invocation.native_trigger_context is None:
        return amount
    trigger = invocation.native_trigger_context
    if not isinstance(trigger, dict):
        raise ValueError("Missing native triggering maximum source descriptor")
    try:
        # eWu replay includes its separately typed state-controller metadata.
        # These fields do not change the underlying Qe identity or amount.
        controller_fields = {"native_apply_state_reference", "native_source_is_eWu"}
        descriptor = NativeEventSource(
            **{
                key: value
                for key, value in trigger.items()
                if key not in controller_fields
            }
        )
        descriptor.validate()
        if (
            type(descriptor.effect_action_id) is not int
            or descriptor.effect_action_id <= 0
        ):
            raise ValueError("Missing actual native maximum source runner family")
    except (TypeError, ValueError) as error:
        raise ValueError(
            "Missing native triggering maximum source/value authority"
        ) from error
    source = triggering_runner_source()
    if source is None:
        # Retained replay attests this actual application source snapshot.
        return descriptor.value
    if not isinstance(source, NativeEventSource):
        raise ValueError("Missing native triggering maximum live source")
    source.validate()
    if (source.uid, source.generic_effect, source.effect_action_id) != (
        descriptor.uid,
        descriptor.generic_effect,
        descriptor.effect_action_id,
    ):
        raise ValueError("Native triggering maximum source identity mismatch")
    runner = source.runner_modifier
    if runner is None:
        return source.value
    if (
        not isinstance(runner, NativeRunnerAmount)
        or runner.uid != source.uid
        or runner.family != source.effect_action_id
        or type(runner.value) is not int
        or not -(1 << 31) <= runner.value < (1 << 31)
    ):
        raise ValueError("Missing native triggering maximum live amount authority")
    return runner.value


def maximum_calculated_amount(amount, invocation):
    """eWN.C offsets92..153 doubles positive PS.fLP before context forcing.

    Null and nonpositive sources retain -2 as a literal amount; imul wraps.
    """
    if amount != -2 or invocation.native_trigger_context is None:
        return amount
    # Reuse the actual scoped Qe identity/value checks, without applying SQ.
    source_value = maximum_application_amount(-1, invocation, context_applied=True)
    return _int32(source_value * 2) if source_value > 0 else amount


@lru_cache(maxsize=1)
def maximum_event_catalog():
    return protocol_catalog.load(DATA_ROOT / "native-maximum-resource-events.json")[
        "effects"
    ]


class NativeMaximumResourceHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng=None):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.rng, self.event_lifecycle = rng, None
        self.prepared_maxima, self.runner_amounts = {}, {}

    def _context(self, effect, invocation):
        if effect["effect_class"] not in FAMILIES or len(effect["parameters"]) != 6:
            raise ValueError("Unsupported native eWN resource definition")
        if registered_or_detached_actor(self.fight, invocation.target_id) is None or (
            not constructor_stat_context(self.fight, invocation)
            and (
                self.fight.phase != "active"
                or invocation.target_id not in self.fight.actors
                or invocation.caster_id not in self.fight.actors
            )
        ):
            raise ValueError("Invalid native maximum resource actors/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native maximum execution/guards")
        return context

    def _events(self, effect):
        family = effect["effect_class"]
        row = maximum_event_catalog().get(str(family))
        masks = effect.get("target_masks")
        if (
            row is None
            or row["runner"] != "eWN"
            or row["fixed_stat_id"] != FAMILIES[family][0]
            or not isinstance(masks, (list, tuple))
            or len(masks) < 7
        ):
            raise ValueError("Missing original eWN source event authority")
        return tuple(sorted({*row["events"], *(masks[6] or ())}))

    def _calculate(self, effect, invocation):
        from .combat_value_transfer import apply_context_value

        context = self._context(effect, invocation)
        amount, apply_current, remove_current = [
            parameter_value(effect["parameters"], i, invocation.level) for i in range(3)
        ]
        amount = maximum_calculated_amount(amount, invocation)
        amount = apply_context_value(
            amount,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return context, amount, apply_current, remove_current

    def cancel_prepared(self, invocation):
        uid = invocation.native_running_uid
        self.prepared_maxima.pop(uid, None)
        self.runner_amounts.pop(uid, None)

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        self._context(effect, invocation)
        events = self._events(effect)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
            self.runner_amounts[uid] = runner
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=1,
                _event_ids=events,
                runner_modifier=runner,
            )
            calculated = self._calculate(effect, invocation)
            self.prepared_maxima[uid] = calculated
            runner.set_calculated(calculated[1])
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        try:
            return self._apply(effect, values, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, values, invocation):
        family = FAMILIES.get(effect["effect_class"])
        uid = invocation.native_running_uid
        if uid is None:
            context, amount, apply_current, remove_current = self._calculate(
                effect, invocation
            )
        else:
            if uid not in self.prepared_maxima:
                raise ValueError("Missing prepared native maximum runner")
            context, amount, apply_current, remove_current = self.prepared_maxima.pop(
                uid
            )
        runner = self.runner_amounts.get(uid)
        if not context.executable:
            return False
        if uid is None and self.event_lifecycle is not None:
            uid = self.allocate_uid()
        if runner is None and self.event_lifecycle is not None:
            runner = NativeRunnerAmount(
                uid, effect["effect_class"], rng=self.rng, value=amount
            )
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=amount,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            live_context = self._context(effect, invocation)
            if not live_context.executable:
                return False
            if live_context.retained != context.retained:
                raise ValueError(
                    "Native maximum retention changed during synchronous L2"
                )
        amount = maximum_application_amount(
            amount if runner is None else runner.value, invocation, context_applied=True
        )
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        stat, cap = family
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, stat
        )
        flags = effect.get("native_effect_flags")
        if cap is not None and not isinstance(flags, (list, tuple)):
            raise ValueError("Missing native maximum effect flags")
        if cap is not None and 17 not in flags:
            amount = min(_int32(cap - raw), amount)
        updated_raw = (
            raw if raw == (1 << 31) - 1 else max(raw_min, _int32(raw + amount))
        )
        updated = effective_maximum(updated_raw, percent, low, high)
        actual = _int32(updated_raw - raw)
        effective_delta = _int32(updated - maximum)
        # PA.op clamps current first; PA.nG then applies effective maximum delta.
        after = current if stat in actor.effect_frozen else min(current, updated)
        if apply_current and stat not in actor.effect_frozen:
            after = max(minimum, min(updated, _int32(after + effective_delta)))

        uid = uid or self.allocate_uid()

        def payload_for(value):
            payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=actor.id,
                value=value,
                timing_payload=context.timing_payload,
            )
            additional = (
                _integer(10, effective_delta)
                + _integer(31, int(bool(apply_current)))
                + _integer(32, int(bool(remove_current)))
            )
            return payload + b"\x42" + _varint(len(additional)) + additional

        payload = payload_for(actual)
        from .combat_resource_pa_notifications import notify_resource_pa
        from .combat_hp_raw import (
            hp_raw_present,
            set_hp_raw_maximum,
            shift_hp_raw_current,
        )

        if stat == 1 and hp_raw_present(actor):
            if raw != (1 << 31) - 1:
                set_hp_raw_maximum(actor, updated_raw)
            if apply_current and effective_delta != 0:
                shift_hp_raw_current(actor, effective_delta)
        elif stat == 14 and getattr(actor, "native_copy_pa_source", None) is not None:
            from .combat_copied_pa import set_copied_maximum, shift_copied_current

            if raw != (1 << 31) - 1:
                set_copied_maximum(self.fight, actor, stat, updated_raw)
            if apply_current and effective_delta != 0:
                shift_copied_current(self.fight, actor, stat, effective_delta)
        elif (
            stat in (2, 3)
            and getattr(actor, "effect_resource_raw_currents", None) is not None
        ):
            from .combat_resource_pa_notifications import (
                set_resource_maximum,
                shift_resource_current,
            )

            if raw != (1 << 31) - 1:
                set_resource_maximum(self.fight, actor, stat, updated_raw)
            if apply_current and effective_delta != 0:
                shift_resource_current(self.fight, actor, stat, effective_delta)
        else:
            intermediate = (
                current if stat in actor.effect_frozen else min(current, updated)
            )
            _write(actor, stat, intermediate, updated_raw, updated)
            if raw != (1 << 31) - 1:
                notify_resource_pa(self.fight, actor, stat, maximum=True)
            _write(actor, stat, after, updated_raw, updated)
            notify_resource_pa(self.fight, actor, stat, before_current=intermediate)
        if runner is not None:
            runner.set_applied(actual)
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family="eWN",
                stat_id=stat,
                actual=actual,
                effective_delta=effective_delta,
                remove_current=bool(remove_current),
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        if runner is None or not runner.notification_suppressed:
            self.packets.append(
                evaluated_effect_delivery(
                    self.fight.id,
                    self.action_id,
                    retained=context.retained,
                    effect_class=effect["effect_class"],
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
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=actual if runner is None else runner.value,
                    channel=channel,
                    _event_ids=self._events(effect),
                    runner_modifier=runner,
                )
        final = actual if runner is None else runner.value
        if context.retained:
            entry = self.fight.owned_stat_effects[uid]
            entry["actual"], entry["payload"] = final, payload_for(final).hex()
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, final)
        return True


def remove_maximum_resource(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = registered_or_detached_actor(handler.fight, entry["target_id"])
    if actor is None:
        raise ValueError("Missing native maximum resource removal actor")
    stat = entry["stat_id"]
    current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(actor, stat)
    updated_raw = (
        raw if raw == (1 << 31) - 1 else max(raw_min, _int32(raw - entry["actual"]))
    )
    updated = effective_maximum(updated_raw, percent, low, high)
    # eWN.bbR uses raw applied amount for ordinary PCs. HP alone uses rCn,
    # capped to current-1 when it exceeds current, to preserve one HP.
    current_removal = entry["actual"]
    if stat == 1:
        current_removal = (
            current - 1
            if entry["effective_delta"] > current
            else entry["effective_delta"]
        )
    after = current
    if stat not in actor.effect_frozen:
        if entry["remove_current"]:
            after = max(minimum, min(maximum, _int32(current - current_removal)))
        after = min(after, updated)
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    from .combat_resource_pa_notifications import notify_resource_pa
    from .combat_hp_raw import hp_raw_present, set_hp_raw_maximum, shift_hp_raw_current

    if stat == 1 and hp_raw_present(actor):
        if entry["remove_current"]:
            shift_hp_raw_current(actor, current_removal, subtract=True)
        if raw != (1 << 31) - 1:
            set_hp_raw_maximum(actor, updated_raw)
    elif stat == 14 and getattr(actor, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import set_copied_maximum, shift_copied_current

        if entry["remove_current"]:
            shift_copied_current(
                handler.fight, actor, stat, current_removal, subtract=True
            )
        if raw != (1 << 31) - 1:
            set_copied_maximum(handler.fight, actor, stat, updated_raw)
    elif (
        stat in (2, 3)
        and getattr(actor, "effect_resource_raw_currents", None) is not None
    ):
        from .combat_resource_pa_notifications import (
            set_resource_maximum,
            shift_resource_current,
        )

        if entry["remove_current"]:
            shift_resource_current(
                handler.fight, actor, stat, current_removal, subtract=True
            )
        if raw != (1 << 31) - 1:
            set_resource_maximum(handler.fight, actor, stat, updated_raw)
    else:
        before_maximum_write = current
        if stat not in actor.effect_frozen and entry["remove_current"]:
            before_maximum_write = max(
                minimum, min(maximum, _int32(current - current_removal))
            )
        _write(actor, stat, before_maximum_write, raw, maximum)
        notify_resource_pa(handler.fight, actor, stat, before_current=current)
        _write(actor, stat, after, updated_raw, updated)
        if raw != (1 << 31) - 1:
            notify_resource_pa(handler.fight, actor, stat, maximum=True)
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))


REDUCTION_FAMILIES = {56: 2, 57: 3, 192: 4}


class NativeMaximumReductionHandler:
    """eWO shifts both raw PA bounds; unlike eWN stores requested amount.

    Chance<100 requires independent UK.pT-compatible transaction RNG callback.
    Parameter flags2/3 equal1 enable restore/reduce current, default true.
    """

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, probability=None
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.probability = probability

    def __call__(self, effect, values, invocation):
        stat = REDUCTION_FAMILIES.get(effect["effect_class"])
        parameters = effect["parameters"]
        if stat is None or len(parameters) not in (2, 4, 6, 8):
            raise ValueError("Unsupported native eWO resource definition")
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        if actor is None or (
            not constructor_stat_context(self.fight, invocation)
            and (
                self.fight.phase != "active"
                or invocation.target_id not in self.fight.actors
                or invocation.caster_id not in self.fight.actors
            )
        ):
            raise ValueError("Invalid native reduction resource actors/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native maximum reduction guards")
        if type(context.executable) is not bool or type(context.retained) is not bool:
            raise ValueError("Unknown native reduction execution")
        if not context.executable:
            return False
        parsed = [
            parameter_value(parameters, i, invocation.level)
            for i in range(len(parameters) // 2)
        ]
        amount = parsed[0]
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, stat
        )
        if amount == -1:
            if type(context.trigger_value) is not int:
                raise ValueError("Missing native triggering reduction amount")
            amount = context.trigger_value
        elif amount == -2:
            amount = current  # eWO.C PV.c(resource), current not maximum.
        chance = (
            100 if len(parsed) < 2 or parsed[1] < 0 else max(0, min(100, parsed[1]))
        )
        if chance < 100:
            if not callable(self.probability):
                raise ValueError("Missing native eWO chance RNG")
            accepted = self.probability(chance, invocation)
            if type(accepted) is not bool:
                raise ValueError("Unknown native reduction chance result")
            if not accepted:
                return False
        restore = len(parsed) < 3 or parsed[2] == 1
        reduce = len(parsed) < 4 or parsed[3] == 1
        after = current
        new_raw, new_min = raw, raw_min
        if maximum != (1 << 31) - 1:
            # PA.oq(-amount): preserve MIN sentinel and clamp raw minimum <= maximum.
            new_min = (
                raw_min if raw_min == -(1 << 31) else min(raw, _int32(raw_min - amount))
            )
            after = max(after, max(low, min(high, new_min)))
            # PA.op(-amount): preserve MAX sentinel and clamp raw maximum >= new raw minimum.
            new_raw = (
                raw if raw == (1 << 31) - 1 else max(new_min, _int32(raw - amount))
            )
            new_maximum = effective_maximum(new_raw, percent, low, high)
            after = min(after, new_maximum)
        else:
            new_maximum = maximum
        new_minimum = max(low, min(high, new_min))
        if reduce:
            remaining = _int32(amount - _int32(current - after))
            after = max(new_minimum, min(new_maximum, _int32(after - remaining)))
        uid = self.allocate_uid()
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
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=effect["effect_class"],
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        if (
            stat in (2, 3)
            and getattr(actor, "effect_resource_raw_currents", None) is not None
        ):
            from .combat_resource_pa_notifications import (
                set_resource_minimum,
                set_resource_maximum,
                shift_resource_current,
            )

            if maximum != (1 << 31) - 1:
                if raw_min != -(1 << 31):
                    set_resource_minimum(self.fight, actor, stat, new_min)
                if raw != (1 << 31) - 1:
                    set_resource_maximum(self.fight, actor, stat, new_raw)
            if reduce:
                remaining = _int32(amount - _int32(current - actor.effect_stats[stat]))
                shift_resource_current(
                    self.fight, actor, stat, remaining, subtract=True
                )
        else:
            from .combat_resource_pa_notifications import notify_resource_pa

            if maximum != (1 << 31) - 1:
                actor.effect_base_minima[stat] = new_min
                actor.effect_minima[stat] = new_minimum
                after_minimum = max(current, new_minimum)
                _write(actor, stat, after_minimum, raw, maximum)
                if raw_min != -(1 << 31):
                    notify_resource_pa(self.fight, actor, stat, maximum=True)
                after_maximum = min(after_minimum, new_maximum)
                _write(actor, stat, after_maximum, new_raw, new_maximum)
                if raw != (1 << 31) - 1:
                    notify_resource_pa(self.fight, actor, stat, maximum=True)
            else:
                after_maximum = current
            _write(actor, stat, after, new_raw, new_maximum)
            notify_resource_pa(self.fight, actor, stat, before_current=after_maximum)
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family="eWO",
                stat_id=stat,
                actual=amount,
                restore_current=restore,
                reduce_current=reduce,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            (
                12613,
                evaluated_application_from_observation(
                    packet, execute=not context.retained
                ),
            )
        )
        return True


def remove_maximum_reduction(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = registered_or_detached_actor(handler.fight, entry["target_id"])
    if actor is None:
        raise ValueError("Missing native maximum resource removal actor")
    stat = entry["stat_id"]
    current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(actor, stat)
    amount = entry["actual"]
    # Native bbR: restore maximum, then minimum, then optionally current.
    new_raw = raw if raw == (1 << 31) - 1 else max(raw_min, _int32(raw + amount))
    new_maximum = effective_maximum(new_raw, percent, low, high)
    after = min(current, new_maximum)
    new_min = (
        raw_min if raw_min == -(1 << 31) else min(new_raw, _int32(raw_min + amount))
    )
    new_minimum = max(low, min(high, new_min))
    after = max(after, new_minimum)
    if entry["restore_current"]:
        after = max(new_minimum, min(new_maximum, _int32(after + amount)))
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    if (
        stat in (2, 3)
        and getattr(actor, "effect_resource_raw_currents", None) is not None
    ):
        from .combat_resource_pa_notifications import (
            set_resource_minimum,
            set_resource_maximum,
            shift_resource_current,
        )

        if raw != (1 << 31) - 1:
            set_resource_maximum(handler.fight, actor, stat, new_raw)
        if raw_min != -(1 << 31):
            set_resource_minimum(handler.fight, actor, stat, new_min)
        if entry["restore_current"]:
            shift_resource_current(handler.fight, actor, stat, amount)
    else:
        from .combat_resource_pa_notifications import notify_resource_pa

        after_maximum = min(current, new_maximum)
        _write(actor, stat, after_maximum, new_raw, new_maximum)
        if raw != (1 << 31) - 1:
            notify_resource_pa(handler.fight, actor, stat, maximum=True)
        actor.effect_base_minima[stat] = new_min
        actor.effect_minima[stat] = new_minimum
        after_minimum = max(after_maximum, new_minimum)
        _write(actor, stat, after_minimum, new_raw, new_maximum)
        if raw_min != -(1 << 31):
            notify_resource_pa(handler.fight, actor, stat, maximum=True)
        _write(actor, stat, after, new_raw, new_maximum)
        notify_resource_pa(handler.fight, actor, stat, before_current=after_minimum)
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))


class NativePercentageHPHandler:
    """986/eZI: additive maximum percentage, HP current protection leaves1.

    Native writer calls il.y twice: field35 ends as applyCurrent, field34 absent.
    Server preserves actual restoreCurrent separately; don't invent corrected wire.
    """

    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.event_lifecycle = None

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 986 or len(effect["parameters"]) not in (2, 6):
            raise ValueError("Unsupported native eZI HP definition")
        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        if (
            actor is None
            or actor.hp <= 0
            or (
                not constructor_stat_context(self.fight, invocation)
                and (
                    self.fight.phase != "active"
                    or invocation.target_id not in self.fight.actors
                    or invocation.caster_id not in self.fight.actors
                )
            )
        ):
            raise ValueError("Invalid native percentage HP actor/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native percentage guards")
        if type(context.executable) is not bool or type(context.retained) is not bool:
            raise ValueError("Unknown native percentage execution")
        if not context.executable:
            return False
        parsed = [
            parameter_value(effect["parameters"], i, invocation.level)
            for i in range(len(effect["parameters"]) // 2)
        ]
        amount = parsed[0]
        apply = len(parsed) < 3 or parsed[1] == 1
        restore = len(parsed) >= 3 and parsed[2] == 1
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, 1
        )
        updated_percent = _int32(percent + amount)
        updated = effective_maximum(raw, updated_percent, low, high)
        delta = _int32(updated - maximum)
        after = current
        if apply:
            applied = -(current - 1) if -delta > current else delta
            after = (
                updated
                if applied > updated - current
                else max(minimum, min(high, _int32(current + applied)))
            )
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=_int32(updated_percent - percent),
            timing_payload=context.timing_payload,
        )
        additional = _integer(35, int(apply))
        payload += b"\x42" + _varint(len(additional)) + additional
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=986,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        from .combat_hp_raw import (
            hp_raw_present,
            set_hp_raw_percentage,
            shift_hp_raw_current,
        )

        if hp_raw_present(actor):
            set_hp_raw_percentage(actor, updated_percent)
            if apply:
                # eZI reads PA.aYS after om has changed the effective maximum.
                applied = -(actor.hp - 1) if -delta > actor.hp else delta
                shift_hp_raw_current(actor, applied)
            after = actor.hp
        else:
            actor.effect_percentages[1] = updated_percent
            actor.effect_maxima[1] = updated
            actor.max_hp = updated
            actor.hp = after
            actor.effect_stats[1] = after
        if current > 0 and after == 0:
            self.fight._event(
                "percentage_hp_update",
                target_id=actor.id,
                source_id=invocation.caster_id,
                effect_class=986,
                uid=uid,
                hp_before=current,
                hp=after,
                maximum=updated,
            )
            self.fight._event("death", actor_id=actor.id)
            if hasattr(self.fight, "native_global_pv_collections"):
                from .combat_global_pv_collections import set_global_fighter_status

                set_global_fighter_status(self.fight, actor.id, "OFF_PLAY")
            death = getattr(self.event_lifecycle, "death", None)
            if callable(death):
                death(
                    actor.id,
                    effect=effect,
                    invocation=invocation,
                    uid=uid,
                    value=_int32(updated_percent - percent),
                )
            if not self.fight._resolution_depth:
                self.fight._settle_deaths()
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=986,
                family="eZI",
                stat_id=1,
                actual=_int32(updated_percent - percent),
                restore_current=restore,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            (
                12613,
                evaluated_application_from_observation(
                    packet, execute=not context.retained
                ),
            )
        )
        return True


def remove_percentage_hp(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = registered_or_detached_actor(handler.fight, entry["target_id"])
    if actor is None:
        raise ValueError("Missing native maximum resource removal actor")
    current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(actor, 1)
    updated_percent = _int32(percent - entry["actual"])
    updated = effective_maximum(raw, updated_percent, low, high)
    after = current
    if entry["restore_current"] and current > 0:
        delta = _int32(updated - maximum)
        reduction = current - 1 if delta > current else delta
        after = max(minimum, min(high, _int32(current - reduction)))
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=986,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    from .combat_hp_raw import (
        hp_raw_present,
        set_hp_raw_percentage,
        shift_hp_raw_current,
    )

    if hp_raw_present(actor):
        set_hp_raw_percentage(actor, updated_percent)
        if entry["restore_current"] and actor.hp > 0:
            delta = _int32(updated - maximum)
            reduction = actor.hp - 1 if delta > actor.hp else delta
            shift_hp_raw_current(actor, reduction, subtract=True)
    else:
        actor.effect_percentages[1] = updated_percent
        actor.effect_maxima[1] = updated
        actor.max_hp = updated
        actor.hp = after
        actor.effect_stats[1] = after
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
