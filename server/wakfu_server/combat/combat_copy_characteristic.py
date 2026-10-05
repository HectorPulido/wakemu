"""Native eWZ copy preparation; application uses max then current PA setters.

eVi1001/eWZ.bbE samples the caster at application time. The captured maximum
and current are distinct; removing the effect does not reverse either setter.
This calculation alone does not implement subscription delivery or ownership.
"""
from dataclasses import dataclass
from .combat_parameters import parameter_value, _float32
from .combat_maximum_resource import _int32
from .combat_resource_loss import stochastic_native_round


@dataclass(frozen=True)
class CopiedCharacteristic:
    stat_id: int
    current: int
    maximum: int


def prepare_copy(parameters, level, *, caster_current, caster_maximum, rng):
    if len(parameters) not in (2, 4):
        raise ValueError("Native eWZ needs a characteristic ID and optional ratio")
    for value in (caster_current, caster_maximum):
        if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
            raise ValueError("Missing native caster characteristic snapshot")
    stat = parameter_value(parameters, 0, level) & 255
    ratio = parameter_value(parameters, 1, level) if len(parameters) == 4 else 100
    draw = rng if callable(rng) else rng.random

    def scaled(value):
        return stochastic_native_round(
            _float32(_float32(_int32(value * ratio)) / _float32(100)), draw
        )

    # Native sentinel applies only to maximum; current still executes imul.
    maximum = 2147483647 if caster_maximum == 2147483647 else scaled(caster_maximum)
    current = scaled(caster_current)
    return CopiedCharacteristic(stat, current, maximum)


class NativeCopyCharacteristicHandler:
    """eWZ application with explicit current/max snapshots and owned wire data."""

    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context, self.rng = (
            action_id,
            allocate_uid,
            context,
            rng,
        )

    def __call__(self, effect, values, invocation):
        from .combat_maximum_resource import _snapshot, effective_maximum
        from .combat_parameter_maximum import _write
        from .combat_actor_snapshot import native_actor_catalog
        from .combat_stat_handler import StatExecutionContext
        from .combat_stat_effects import owned_effect_payload, owned_effect_application
        from .combat_effects import _integer, _varint

        if effect["effect_class"] != 1001 or len(effect["parameters"]) not in (2, 4):
            raise ValueError("Unsupported native eWZ definition")
        caster = self.fight.actors.get(invocation.caster_id)
        target = self.fight.actors.get(invocation.target_id)
        if caster is None or target is None or self.fight.phase != "active":
            raise ValueError("Invalid native copied characteristic actors")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Unverified native copied characteristic guards")
        if not ctx.executable:
            return False
        stat = parameter_value(effect["parameters"], 0, invocation.level) & 255
        row = native_actor_catalog()["characteristics"].get(str(stat))
        if row is None:
            raise ValueError("Unknown native copied characteristic")
        source = _snapshot(caster, stat)
        before, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            target, stat
        )
        copied = prepare_copy(
            effect["parameters"],
            invocation.level,
            caster_current=source[0],
            caster_maximum=source[2],
            rng=self.rng,
        )
        # PA.or sets raw maximum first; PA.on then clamps the sampled current.
        updated_raw = max(raw_min, copied.maximum)
        updated = effective_maximum(updated_raw, percent, low, high)
        after = max(
            minimum, min(high if row["expandable"] else updated, copied.current)
        )
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=caster.id,
            target_id=target.id,
            value=copied.current,
            timing_payload=ctx.timing_payload,
        )
        extra = _integer(10, copied.maximum) + _integer(12, stat)
        payload += b"\x42" + _varint(len(extra)) + extra
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=1001,
            target_id=target.id,
            uid=uid,
            running_effect_payload=payload,
        )
        _write(target, stat, after, updated_raw, updated)
        self.fight._event(
            "characteristic_changed",
            source_id=caster.id,
            target_id=target.id,
            stat_id=stat,
            actual=after - before,
            current=after,
        )
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=target.id,
                caster_id=caster.id,
                effect_class=1001,
                family="eWZ",
                stat_id=stat,
                actual=copied.current,
                copied_maximum=copied.maximum,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        self.packets.append((13497, packet))
        return True


def remove_copied_characteristic(handler, uid):
    from .combat_effect_removal import running_effect_removal

    entry = handler.fight.owned_stat_effects[uid]
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=1001,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
