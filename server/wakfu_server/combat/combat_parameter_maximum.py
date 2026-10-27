"""eWU/eWS1201/eWT1202 parameter-selected maximum, without class wrappers.

Native eWS/eWT use EFFECTIVE max as input to PA.or (raw assignment).
This intentionally differs from eWN, especially with percentages/hard caps.
On a subtract-underflow they set raw min THEN rewrite amount=max-min; this
native value may be zero and removal must not invent the lost amount.
"""
from .combat_parameters import parameter_value
from .combat_maximum_resource import _snapshot, _int32, effective_maximum
from .combat_actor_snapshot import native_actor_catalog
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


def transition(
    *,
    family,
    removing,
    amount,
    current,
    maximum,
    minimum,
    raw_min,
    percent,
    low,
    high,
    expandable
):
    subtract = (family == 1202) != removing
    candidate = _int32(maximum - amount if subtract else maximum + amount)
    underflow = subtract and candidate < minimum
    raw = max(raw_min, minimum if underflow else candidate)
    updated = effective_maximum(raw, percent, low, high)
    stored = _int32(updated - minimum) if underflow else amount
    after = current if expandable else min(current, updated)
    return after, raw, updated, stored


def _write(actor, stat, current, raw, maximum):
    actor.effect_stats[stat] = current
    actor.effect_base_maxima[stat] = raw
    actor.effect_maxima[stat] = maximum
    from .combat_hupper_resource_binding import maximum_changed

    maximum_changed(actor, stat)
    if stat in (1, 2, 3):
        attr = {1: "hp", 2: "ap", 3: "mp"}[stat]
        setattr(actor, attr, current)
        setattr(actor, "max_" + attr, maximum)


class NativeParameterMaximumHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.event_lifecycle = None

    def __call__(self, effect, values, invocation):
        family = effect["effect_class"]
        if family not in (1201, 1202) or len(effect["parameters"]) != 4:
            raise ValueError("Unsupported native eWU definition")
        actor = self.fight.actors.get(invocation.target_id)
        if (
            actor is None
            or invocation.caster_id not in self.fight.actors
            or self.fight.phase != "active"
        ):
            raise ValueError("Invalid native eWU actors/fight")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Unverified native eWU guards")
        if not ctx.executable:
            return False
        stat = parameter_value(effect["parameters"], 0, invocation.level) & 255
        amount = parameter_value(effect["parameters"], 1, invocation.level)
        row = native_actor_catalog()["characteristics"].get(str(stat))
        if row is None:
            raise ValueError("Unknown native eWU characteristic")
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, stat
        )
        uid = self.allocate_uid()
        from .combat_maximum_characteristic_events import (
            MAXIMUM_EVENTS,
            capture_source,
            notify,
            notify_intent,
        )

        event_source = (
            capture_source(self.event_lifecycle, effect, invocation, uid)
            if stat in MAXIMUM_EVENTS
            else None
        )
        if notify_intent(
            self.event_lifecycle,
            self.fight,
            actor,
            stat,
            effect=effect,
            invocation=invocation,
            uid=uid,
            value=amount,
        ):
            # L2 reactions precede the actual setter, and can invalidate it or
            # change PA. Read the resulting authority/snapshot exactly as it
            # now exists; never apply a transition calculated before callbacks.
            if (
                self.fight.actors.get(invocation.target_id) is not actor
                or invocation.caster_id not in self.fight.actors
            ):
                return False
            ctx = self.context(effect, invocation)
            if (
                not isinstance(ctx, StatExecutionContext)
                or ctx.source_guards_verified is not True
                or type(ctx.executable) is not bool
                or type(ctx.retained) is not bool
            ):
                raise ValueError("Unverified native eWU guards after L2")
            if not ctx.executable:
                return False
            current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
                actor, stat
            )
        after, updated_raw, updated, stored = transition(
            family=family,
            removing=False,
            amount=amount,
            current=current,
            maximum=maximum,
            minimum=minimum,
            raw_min=raw_min,
            percent=percent,
            low=low,
            high=high,
            expandable=row["expandable"],
        )
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=stored,
            timing_payload=ctx.timing_payload,
        )
        extra = _integer(12, stat)
        payload += b"\x42" + _varint(len(extra)) + extra
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=family,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        from .combat_hp_raw import hp_raw_present, set_hp_raw_maximum

        if stat == 1 and hp_raw_present(actor):
            set_hp_raw_maximum(actor, updated_raw)
        elif (
            stat in (2, 3)
            and getattr(actor, "effect_resource_raw_currents", None) is not None
        ):
            from .combat_resource_pa_notifications import set_resource_maximum

            set_resource_maximum(self.fight, actor, stat, updated_raw)
        else:
            _write(actor, stat, after, updated_raw, updated)
            from .combat_resource_pa_notifications import notify_resource_pa

            notify_resource_pa(self.fight, actor, stat, maximum=True)
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=family,
                family="eWU",
                stat_id=stat,
                actual=stored,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
            if event_source is not None:
                self.fight.owned_stat_effects[uid][
                    "maximum_event_source"
                ] = event_source
        self.packets.append((13497, packet))
        if event_source is not None:
            if ctx.retained:
                self.event_lifecycle.register_applied(effect, invocation, uid)
            notify(
                self.event_lifecycle,
                self.fight,
                actor,
                stat,
                maximum,
                effect=effect,
                invocation=invocation,
                uid=uid,
                value=stored,
            )
        return True


def remove_parameter_maximum(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = handler.fight.actors[entry["target_id"]]
    stat = entry["stat_id"]
    current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(actor, stat)
    from .combat_maximum_characteristic_events import inverse_source, notify

    event_source = inverse_source(handler, entry)
    row = native_actor_catalog()["characteristics"][str(stat)]
    after, updated_raw, updated, _ = transition(
        family=entry["effect_class"],
        removing=True,
        amount=entry["actual"],
        current=current,
        maximum=maximum,
        minimum=minimum,
        raw_min=raw_min,
        percent=percent,
        low=low,
        high=high,
        expandable=row["expandable"],
    )
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    from .combat_hp_raw import hp_raw_present, set_hp_raw_maximum

    if stat == 1 and hp_raw_present(actor):
        set_hp_raw_maximum(actor, updated_raw)
    elif (
        stat in (2, 3)
        and getattr(actor, "effect_resource_raw_currents", None) is not None
    ):
        from .combat_resource_pa_notifications import set_resource_maximum

        set_resource_maximum(handler.fight, actor, stat, updated_raw)
    else:
        _write(actor, stat, after, updated_raw, updated)
        from .combat_resource_pa_notifications import notify_resource_pa

        notify_resource_pa(handler.fight, actor, stat, maximum=True)
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
    if event_source is not None:
        effect, invocation = event_source
        notify(
            handler.event_lifecycle,
            handler.fight,
            actor,
            stat,
            maximum,
            effect=effect,
            invocation=invocation,
            uid=uid,
            value=entry["actual"],
        )
