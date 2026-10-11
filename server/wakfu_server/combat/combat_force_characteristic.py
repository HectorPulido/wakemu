"""eYO fixed-PC assignments: setters clamp, removal never reverses them."""
from .combat_parameters import parameter_value
from .combat_maximum_resource import _snapshot, _int32, effective_maximum
from .combat_parameter_maximum import _write
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_resource_loss import stochastic_native_round
from wakfu_server.equipment_damage import _float
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


def forced_parameters(parameters, level, *, caster_current, target_maximum, rng):
    if len(parameters) not in (0, 2, 4, 6):
        raise ValueError("Unsupported native eYO parameter count")
    value = parameter_value(parameters, 0, level) if parameters else caster_current
    maximum = len(parameters) >= 4 and parameter_value(parameters, 1, level) == 1
    percent = len(parameters) >= 6 and parameter_value(parameters, 2, level) == 1
    if percent:
        value = stochastic_native_round(
            _float(_float(_int32(target_maximum * value)) / _float(100)),
            (rng if callable(rng) else rng.random),
        )
    return value, maximum, percent


def forced_transition(
    *,
    value,
    set_maximum,
    current,
    raw,
    maximum,
    minimum,
    raw_min,
    percent,
    low,
    high,
    over_max_current
):
    if set_maximum:
        raw = max(raw_min, value)
        maximum = effective_maximum(raw, percent, low, high)
    # fff.on tests PC.fZB, independently of isExpandable.
    current = max(minimum, min(high if over_max_current else maximum, value))
    return current, raw, maximum


class NativeForcedCharacteristicHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, registry, *, action_id, allocate_uid, context, rng
    ):
        self.fight, self.packets, self.registry = fight, packets, registry["effects"]
        self.action_id, self.allocate_uid, self.context, self.rng = (
            action_id,
            allocate_uid,
            context,
            rng,
        )

    def __call__(self, effect, values, invocation):
        row = self.registry.get(str(effect["effect_class"]))
        if row is None or row["runner"] != "eYO":
            raise ValueError("Missing native forced characteristic registry")
        from .combat_summon_initialization import registered_or_detached_actor
        from .combat_npc_initialization import constructor_stat_context

        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        caster = registered_or_detached_actor(self.fight, invocation.caster_id)
        constructor = constructor_stat_context(self.fight, invocation)
        if (
            actor is None
            or caster is None
            or (not constructor and self.fight.phase != "active")
        ):
            raise ValueError("Invalid native forced characteristic actors")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Unverified native forced characteristic guards")
        if not ctx.executable:
            return False
        stat = row["fixed_stat_id"]
        from .combat_character_copy_metadata import native_copy_characteristics

        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, stat
        )
        caster_current = _snapshot(caster, stat)[0] if not effect["parameters"] else 0
        value, set_maximum, is_percent = forced_parameters(
            effect["parameters"],
            invocation.level,
            caster_current=caster_current,
            target_maximum=maximum,
            rng=self.rng,
        )
        from .combat_value_transfer import apply_context_value

        value = apply_context_value(
            value,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        after, updated_raw, updated = forced_transition(
            value=value,
            set_maximum=set_maximum,
            current=current,
            raw=raw,
            maximum=maximum,
            minimum=minimum,
            raw_min=raw_min,
            percent=percent,
            low=low,
            high=high,
            over_max_current=native_copy_characteristics()["fresh_characteristics"][
                str(stat)
            ]["over_max_current"],
        )
        uid = self.allocate_uid()
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=caster.id,
            target_id=actor.id,
            value=value,
            timing_payload=ctx.timing_payload,
        )
        additional = _integer(17, int(set_maximum)) + _integer(18, int(is_percent))
        payload += b"\x42" + _varint(len(additional)) + additional
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=effect["effect_class"],
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        from .combat_hp_raw import (
            hp_raw_present,
            set_hp_raw_maximum,
            set_hp_raw_current,
        )
        from .combat_copied_pa import (
            copied_pa_present,
            set_copied_current,
            set_copied_maximum,
        )

        if copied_pa_present(actor):
            if set_maximum:
                set_copied_maximum(self.fight, actor, stat, value)
            set_copied_current(self.fight, actor, stat, value)
            after = actor.effect_stats[stat]
        elif stat == 1 and hp_raw_present(actor):
            if set_maximum:
                set_hp_raw_maximum(actor, value)
            set_hp_raw_current(actor, value)
            after = actor.hp
        elif (
            stat in (2, 3)
            and getattr(actor, "effect_resource_raw_currents", None) is not None
        ):
            from .combat_resource_pa_notifications import (
                set_resource_maximum,
                set_resource_current,
            )

            if set_maximum:
                set_resource_maximum(self.fight, actor, stat, value)
            set_resource_current(self.fight, actor, stat, value)
            after = actor.effect_stats[stat]
        else:
            _write(actor, stat, after, updated_raw, updated)
        self.fight._event(
            "characteristic_changed",
            source_id=caster.id,
            target_id=actor.id,
            stat_id=stat,
            actual=after - current,
            current=after,
        )
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=caster.id,
                effect_class=effect["effect_class"],
                family="eYO",
                stat_id=stat,
                actual=value,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        self.packets.append((13497, packet))
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, value)
        return True


def remove_forced_characteristic(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
