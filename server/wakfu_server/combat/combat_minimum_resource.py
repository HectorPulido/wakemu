"""Native eWV877: set HP minimum; serialize actual reversible minimum delta."""
import struct
import math
from .combat_parameters import parameter_value
from .combat_maximum_resource import _snapshot, _int32
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal


def transition(current, raw_max, raw_min, low, high, amount, *, fresh=True):
    raw = min(
        raw_max, amount if fresh else _int32(max(low, min(high, raw_min)) + amount)
    )
    minimum = max(low, min(high, raw))
    return (
        max(current, minimum),
        raw,
        minimum,
        _int32(minimum - max(low, min(high, raw_min))) if fresh else amount,
    )


class NativeMinimumResourceHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 877 or len(effect["parameters"]) not in (2, 4):
            raise ValueError("Unsupported native eWV definition")
        actor = self.fight.actors.get(invocation.target_id)
        if (
            actor is None
            or invocation.caster_id not in self.fight.actors
            or self.fight.phase != "active"
        ):
            raise ValueError("Invalid native eWV actors")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Unverified native eWV guards")
        if not ctx.executable:
            return False
        current, raw_max, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, 1
        )
        amount = parameter_value(effect["parameters"], 0, invocation.level)
        if (
            len(effect["parameters"]) == 4
            and parameter_value(effect["parameters"], 1, invocation.level) == 1
        ):
            product = _int32(maximum * amount)
            product_float = struct.unpack("f", struct.pack("f", float(product)))[0]
            fraction = struct.unpack("f", struct.pack("f", product_float / 100.0))[0]
            amount = math.ceil(fraction) if fraction > 0 else int(fraction)
        after, raw, new_min, stored = transition(
            current, raw_max, raw_min, low, high, amount
        )
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=stored,
            timing_payload=ctx.timing_payload,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=877,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        from .combat_hp_raw import hp_raw_present, set_hp_raw_minimum

        if hp_raw_present(actor):
            set_hp_raw_minimum(actor, amount)
        else:
            actor.effect_base_minima[1], actor.effect_minima[1] = raw, new_min
            actor.hp = actor.effect_stats[1] = after
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=877,
                family="eWV",
                stat_id=1,
                actual=stored,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        self.packets.append((13497, packet))
        return True


def remove_minimum_resource(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    actor = handler.fight.actors[entry["target_id"]]
    current, raw_max, maximum, minimum, raw_min, percent, low, high = _snapshot(
        actor, 1
    )
    after, raw, new_min, _ = transition(
        current, raw_max, raw_min, low, high, -entry["actual"], fresh=False
    )
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=877,
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    from .combat_hp_raw import hp_raw_present, set_hp_raw_minimum

    if hp_raw_present(actor):
        set_hp_raw_minimum(actor, _int32(minimum - entry["actual"]))
    else:
        actor.effect_base_minima[1], actor.effect_minima[1] = raw, new_min
        actor.hp = actor.effect_stats[1] = after
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
