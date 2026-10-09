"""Native1065/eZe AP and1066/eZg range category modifiers through eZf.

eZf.C reads amount/category parameters; eZe.c adds -amount to eHl.pOJ,
eZe.d adds amount back. eHl uses Java int adjustOrPutValue, retaining zero.
AdditionalDatas ij.getValue is protobuf field10 and outer iN.value is amount.
"""
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


def _int32(value):
    return (value + (1 << 31)) % (1 << 32) - (1 << 31)


def modify(actor, category, delta, *, range_modifier=False):
    snapshot = (
        actor.spell_range_modifiers if range_modifier else actor.spell_ap_cost_modifiers
    )
    if not isinstance(snapshot, dict) or any(
        type(k) is not int or type(v) is not int for k, v in snapshot.items()
    ):
        raise ValueError("Missing native eHl AP modifier snapshot")
    if type(category) is not int or not 1 <= category <= 18 or type(delta) is not int:
        raise ValueError("Invalid native fyU category/amount")
    snapshot[category] = _int32(snapshot.get(category, 0) + delta)


class NativeSpellCostHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] not in (1065, 1066) or len(effect["parameters"]) != 4:
            raise ValueError("Unsupported native eZe definition")
        actor = self.fight.actors.get(invocation.target_id)
        if (
            self.fight.phase != "active"
            or actor is None
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Invalid native eZe actor/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native eZe guards")
        if type(context.executable) is not bool or type(context.retained) is not bool:
            raise ValueError("Unknown native eZe execution/retention")
        if not context.executable:
            return False
        amount = parameter_value(effect["parameters"], 0, invocation.level)
        category = parameter_value(effect["parameters"], 1, invocation.level)
        if category not in range(1, 19):
            return False  # eZf.fRS: invalid category cancels.
        range_modifier = effect["effect_class"] == 1066
        snapshot = (
            actor.spell_range_modifiers
            if range_modifier
            else actor.spell_ap_cost_modifiers
        )
        # Validate before UID allocation or mutation.
        if not isinstance(snapshot, dict) or any(
            type(k) is not int or type(v) is not int for k, v in snapshot.items()
        ):
            raise ValueError("Missing native eHl AP modifier snapshot")
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
        additional = _integer(10, category)
        payload += b"\x42" + _varint(len(additional)) + additional
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=effect["effect_class"],
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        modify(
            actor,
            category,
            amount if range_modifier else _int32(-amount),
            range_modifier=range_modifier,
        )
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family="eZg" if range_modifier else "eZe",
                stat_id=None,
                actual=amount,
                category=category,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append((13497, packet))
        return True


def remove_spell_cost(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry["family"] not in ("eZe", "eZg"):
        raise ValueError("Not an owned native AP modifier")
    actor = handler.fight.actors[entry["target_id"]]
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=entry["effect_class"],
        target_id=actor.id,
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    modify(
        actor,
        entry["category"],
        _int32(-entry["actual"]) if entry["family"] == "eZg" else entry["actual"],
        range_modifier=entry["family"] == "eZg",
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
