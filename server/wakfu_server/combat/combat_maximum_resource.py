"""Native eWN resource maxima31/AP,41/MP,191/WP, with reversible owned data.

eWN.C parameters: amount, applyCurrent, removeCurrent. eWN.c changes raw
PA.aYV maximum, measures effective maximum delta, then optionally applies it
to current. Flag17 bypasses PC.aZt cap (AP16/MP8; WP cap-1=none).
AdditionalDatas31/32 store booleans;10 stores effective maximum delta.
Raw/effective maxima and percentages follow fff.aYU with Java int overflow
and division truncation; raw PA minima must be explicit, never inferred.
"""
from .combat_parameters import parameter_value
from .combat_actor_snapshot import native_actor_catalog
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal

FAMILIES = {31: (2, 16), 41: (3, 8), 191: (4, None)}


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
    if stat in actor.effect_frozen:
        raise ValueError("Frozen PA requires explicit raw current snapshot")
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
    if stat in (2, 3):
        setattr(actor, {2: "ap", 3: "mp"}[stat], current)
        setattr(actor, {2: "max_ap", 3: "max_mp"}[stat], maximum)


class NativeMaximumResourceHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )

    def __call__(self, effect, values, invocation):
        family = FAMILIES.get(effect["effect_class"])
        if family is None or len(effect["parameters"]) != 6:
            raise ValueError("Unsupported native eWN resource definition")
        actor = self.fight.actors.get(invocation.target_id)
        if (
            actor is None
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Invalid native maximum resource actors/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native maximum guards")
        if type(context.executable) is not bool or type(context.retained) is not bool:
            raise ValueError("Unknown native maximum execution")
        if not context.executable:
            return False
        amount, apply_current, remove_current = [
            parameter_value(effect["parameters"], i, invocation.level) for i in range(3)
        ]
        if amount == -1:
            if type(context.trigger_value) is not int:
                raise ValueError("Missing native triggering maximum amount")
            amount = context.trigger_value
        if amount == -2:
            raise ValueError(
                "Native maximum triggering container transform unsupported"
            )
        stat, cap = family
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, stat
        )
        flags = effect.get("native_effect_flags")
        if not isinstance(flags, list):
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
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=actual,
            timing_payload=context.timing_payload,
        )
        additional = (
            _integer(10, effective_delta)
            + _integer(31, int(bool(apply_current)))
            + _integer(32, int(bool(remove_current)))
        )
        payload += b"\x42" + _varint(len(additional)) + additional
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=effect["effect_class"],
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        _write(actor, stat, after, updated_raw, updated)
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
        self.packets.append((13497, packet))
        return True


def remove_maximum_resource(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = handler.fight.actors[entry["target_id"]]
    stat = entry["stat_id"]
    current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(actor, stat)
    updated_raw = (
        raw if raw == (1 << 31) - 1 else max(raw_min, _int32(raw - entry["actual"]))
    )
    updated = effective_maximum(updated_raw, percent, low, high)
    after = current
    if stat not in actor.effect_frozen:
        if entry["remove_current"]:
            after = max(
                minimum, min(maximum, _int32(current - entry["effective_delta"]))
            )
        after = min(after, updated)
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    _write(actor, stat, after, updated_raw, updated)
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
        actor = self.fight.actors.get(invocation.target_id)
        if (
            actor is None
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
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
        actor.effect_base_minima[stat] = new_min
        actor.effect_minima[stat] = new_minimum
        _write(actor, stat, after, new_raw, new_maximum)
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
        self.packets.append((13497, packet))
        return True


def remove_maximum_reduction(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = handler.fight.actors[entry["target_id"]]
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
    actor.effect_base_minima[stat] = new_min
    actor.effect_minima[stat] = new_minimum
    _write(actor, stat, after, new_raw, new_maximum)
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

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 986 or len(effect["parameters"]) not in (2, 6):
            raise ValueError("Unsupported native eZI HP definition")
        actor = self.fight.actors.get(invocation.target_id)
        if (
            actor is None
            or actor.hp <= 0
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
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
        actor.effect_percentages[1] = updated_percent
        actor.effect_maxima[1] = updated
        actor.max_hp = updated
        actor.hp = after
        actor.effect_stats[1] = after
        if current > 0 and after == 0:
            self.fight._event("death", actor_id=actor.id)
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
        self.packets.append((13497, packet))
        return True


def remove_percentage_hp(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = handler.fight.actors[entry["target_id"]]
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
    actor.effect_percentages[1] = updated_percent
    actor.effect_maxima[1] = updated
    actor.max_hp = updated
    actor.hp = after
    actor.effect_stats[1] = after
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
