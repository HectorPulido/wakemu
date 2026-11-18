"""Native eWV minima: serialize the actual reversible PA minimum delta."""
from .combat_source_parent_index import OwnedStateSourceRow
import struct
import math
from .combat_parameters import parameter_value
from .combat_maximum_resource import _snapshot, _int32
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal

FAMILIES = {877: 1, 1003: 14}


def minimum_snapshot(actor, stat):
    if stat == 14 and (
        stat in (getattr(actor, "effect_frozen", None) or ())
        and getattr(actor, "native_copy_pa_source", None) is None
    ):
        raise ValueError(
            "Native eWV characteristic14 needs hidden raw-current authority"
        )
    return _snapshot(actor, stat)


def write_minimum(actor, stat, amount, raw, minimum, current):
    from .combat_hp_raw import hp_raw_present, set_hp_raw_minimum

    if stat == 1 and hp_raw_present(actor):
        set_hp_raw_minimum(actor, amount)
        return
    copied_current = None
    if stat == 14 and getattr(actor, "native_copy_pa_source", None) is not None:
        from .combat_copied_pa import copied_raw_current

        copied_current = copied_raw_current(actor, stat)
    actor.effect_base_minima[stat], actor.effect_minima[stat] = raw, minimum
    if copied_current is not None:
        # fff.ae writes raw minimum even frozen; only mutable PA raises bqD.
        if stat not in actor.effect_frozen:
            copied_current = max(copied_current, minimum)
        actor.effect_characteristic_raw_currents[stat] = copied_current
        current = max(minimum, min(actor.effect_maxima[stat], copied_current))
    actor.effect_stats[stat] = current
    if stat == 1:
        actor.hp = current


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
        if effect["effect_class"] not in FAMILIES or len(effect["parameters"]) not in (
            2,
            4,
        ):
            raise ValueError("Unsupported native eWV definition")
        stat = FAMILIES[effect["effect_class"]]
        from .combat_summon_initialization import registered_or_detached_actor
        from .combat_npc_initialization import constructor_stat_context

        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        from .combat_state_managers import registered_source_pv

        source = registered_source_pv(self.fight, invocation.caster_id)
        area = actor is None
        if area:
            actor, _, _ = _area_hp_operand(self.fight, invocation.target_id, stat)
        constructor = constructor_stat_context(self.fight, invocation)
        if (
            actor is None
            or source is None
            or (self.fight.phase != "active" and not constructor)
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
        (
            current,
            raw_max,
            maximum,
            minimum,
            raw_min,
            percent,
            low,
            high,
        ) = (
            _area_minimum_snapshot(self.fight, actor.id, stat)
            if area
            else minimum_snapshot(actor, stat)
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
            effect_class=effect["effect_class"],
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        if area:
            _write_area_minimum(self.fight, actor.id, stat, raw)
        else:
            write_minimum(actor, stat, amount, raw, new_min, after)
        if ctx.retained:
            self.fight.owned_stat_effects[uid] = OwnedStateSourceRow(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family="eWV",
                stat_id=stat,
                actual=stored,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        self.packets.append((13497, packet))
        return True


def remove_minimum_resource(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    stat = entry["stat_id"]
    if FAMILIES.get(entry["effect_class"]) != stat:
        raise ValueError("Native eWV retained characteristic identity mismatch")
    actor = handler.fight.actors.get(entry["target_id"])
    area = actor is None
    if area:
        actor, _, _ = _area_hp_operand(handler.fight, entry["target_id"], stat)
    current, raw_max, maximum, minimum, raw_min, percent, low, high = (
        _area_minimum_snapshot(handler.fight, actor.id, stat)
        if area
        else minimum_snapshot(actor, stat)
    )
    after, raw, new_min, _ = transition(
        current, raw_max, raw_min, low, high, -entry["actual"], fresh=False
    )
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    if area:
        _write_area_minimum(handler.fight, actor.id, stat, raw)
    else:
        write_minimum(
            actor, stat, _int32(minimum - entry["actual"]), raw, new_min, after
        )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))


def _area_hp_operand(fight, identity, stat):
    """Resolve only the real HP PA supplied by an actual faW constructor."""
    if stat != 1:
        raise ValueError("Unsupported native area minimum characteristic")
    from .combat_state_managers import registered_area_pv, retained_area_pv_row
    from .combat_effect_area import native_effect_areas
    from .combat_fake_fighter_resources import fake_fighter_hp_state

    pv = registered_area_pv(fight, identity)
    row = retained_area_pv_row(fight, identity)
    if pv is None or row is None or row.get("native_area_contract") != "faW":
        raise ValueError("Missing actual faW HP minimum owner")
    state = fake_fighter_hp_state(row, native_effect_areas()[str(row["reference"])])
    return pv, row, state


def _area_minimum_snapshot(fight, identity, stat):
    _, _, hp = _area_hp_operand(fight, identity, stat)
    base = hp["constructor"]
    return (
        hp["current"],
        hp["raw_maximum"],
        hp["maximum"],
        hp["minimum"],
        hp["raw_minimum"],
        hp["percentage"],
        base["absolute_minimum"],
        base["absolute_maximum"],
    )


def _write_area_minimum(fight, identity, stat, raw):
    from .combat_area_hp_pa import _persist

    _, row, hp = _area_hp_operand(fight, identity, stat)
    hp["raw_minimum"] = raw
    if not hp["frozen"]:
        hp["raw_current"] = max(hp["raw_current"], raw)
    _persist(row, hp, "native_faw_hp_current")
