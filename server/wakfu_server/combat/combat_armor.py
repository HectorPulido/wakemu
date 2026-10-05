"""Native eWx1013 armor: coefficients, mastery, cap and eWQ ownership."""
import math
from dataclasses import replace
from .combat_parameters import parameter_value, _float32
from .combat_damage_parameters import damage_mastery_context
from .combat_stat_handler import StatExecutionContext, _current, _bounds, _write
from .combat_stat_effects import (
    apply_current_stat,
    owned_effect_payload,
    owned_effect_application,
)
from .combat_effects import _integer


def _i32(value):
    return ((value + (1 << 31)) % (1 << 32)) - (1 << 31)


def _scaled(value, bonus):
    factor = max(0, _float32(1 + _float32(_float32(bonus) / 100)))
    result = _float32(_float32(value) * factor)
    return max(-(1 << 31), min((1 << 31) - 1, math.floor(result)))


def armor_amount(effect, level, source, target, *, capped_player, additional_final=0):
    raw = effect["parameters"]
    if len(raw) < 2 or len(raw) % 2:
        raise ValueError("Invalid native armor parameter pairs")
    values = [parameter_value(raw, i, level) for i in range(len(raw) // 2)]
    mode = values[1] if len(values) > 1 else 3
    if (
        mode not in range(4)
        or type(capped_player) is not bool
        or type(additional_final) is not int
        or not -(1 << 31) <= additional_final < (1 << 31)
    ):
        raise ValueError("Unknown native armor coefficient/context")
    flags = set(effect["native_effect_flags"])
    if flags - {3, 4, 5, 6, 17, 22, 23, 24}:
        raise ValueError("Unaudited native armor flags")
    source_stats, target_stats = source.effect_stats, target.effect_stats
    if (
        not isinstance(source_stats, dict)
        or not isinstance(target_stats, dict)
        or 97 not in target_stats
    ):
        raise ValueError("Missing authoritative native armor snapshot")
    bonus = source_stats.get(120, 0) if mode in (1, 3) and source.id != target.id else 0
    bonus = _i32(bonus + (target_stats.get(121, 0) if mode in (2, 3) else 0))
    value = _scaled(values[0], bonus)
    if len(values) > 2:
        element = ((values[2] + 128) % 256) - 128
        elemental = {0: None, 1: 21, 2: 22, 3: 23, 4: 24, 5: 90, 6: 109}
        if element not in elemental:
            raise ValueError("Invalid native armor elemental enum")
        if elemental[element] is not None:
            mastery = damage_mastery_context(
                flags,
                source_xy=source.position[:2],
                target_xy=target.position[:2],
                source_radius=source.physical_radius,
                target_radius=target.physical_radius,
                source_total_hp=source.hp + source_stats.get(92, 0),
                source_total_max_hp=source.max_hp + source.effect_maxima.get(92, 0),
            )
            ids = [elemental[element], 20, 52 if effect["variant"] & 1 else 102]
            ids += [
                identity
                for key, identity in (
                    ("single_target", 105),
                    ("area", 106),
                    ("melee", 103),
                    ("ranged", 104),
                    ("berserk", 107),
                )
                if mastery[key]
            ]
            total = 0
            for identity in ids:
                total = _i32(total + source_stats.get(identity, 0))
            value = _scaled(value, total)
    # eWx.C applies SW(mode) after coefficients/mastery, before the cap.
    # fNk resets this transient faq accumulator; mode0 ignores it entirely.
    if mode != 0:
        value = _scaled(value, additional_final)
    maximum = (1 << 31) - 1
    if (
        capped_player
        and 88 in target_stats
        and not (len(values) > 3 and values[3] == 2)
    ):
        multiplied = _i32(target.effect_maxima[1] * target_stats[88])
        fraction = _float32(_float32(multiplied) / 100)
        maximum = max(-(1 << 31), min((1 << 31) - 1, math.floor(fraction + 0.5)))
    room = max(0, _i32(maximum - target_stats[97]))
    return dict(requested=min(room, max(0, value)), room=room)


class NativeArmorHandler:
    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, authority, rng=None
    ):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context, self.authority = (
            allocate_uid,
            context,
            authority,
        )
        self.event_lifecycle = None
        self.prepared = {}
        self.final_modifiers = {}
        self.runner_amounts = {}
        self.rng = rng

    def _calculate(self, effect, invocation, *, additional_final=0):
        source = self.fight.actors[invocation.caster_id]
        target = self.fight.actors[invocation.target_id]
        if self.fight.phase != "active" or self.fight.current is None or target.hp <= 0:
            raise ValueError("Invalid native armor fight/target")
        self.authority(self.fight, source)
        target_authority = self.authority(self.fight, target)
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native armor application guards")
        if not context.executable:
            return context, None
        amount = armor_amount(
            effect,
            invocation.level,
            source,
            target,
            capped_player=target_authority.is_player,
            additional_final=additional_final,
        )
        return context, amount

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        from .combat_final_modifier import NativeFinalModifier

        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        modifier = NativeFinalModifier(uid, 1013)
        from .combat_trigger_value_modifier import NativeRunnerAmount

        runner = NativeRunnerAmount(uid, 1013, rng=self.rng)
        self.runner_amounts[uid] = runner
        self.final_modifiers[uid] = modifier
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=0,
            channel=1,
            final_modifier=modifier,
            runner_modifier=runner,
        )
        self.prepared[uid] = self._calculate(
            effect, invocation, additional_final=modifier.value
        )
        amount = self.prepared[uid][1]
        if amount is not None:
            runner.set_calculated(amount["requested"])
        return invocation

    def __call__(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is None:
            # Qe.k/fNk clones enter without original preparation; rBA resets0.
            context, amount = self._calculate(effect, invocation)
        else:
            if uid not in self.prepared:
                raise ValueError("Missing prepared native armor running effect")
            context, amount = self.prepared.pop(uid)
        modifier = self.final_modifiers.pop(uid, None)
        runner = self.runner_amounts.pop(uid, None)
        if amount is None:
            return False
        if amount["requested"] == 0:
            return False  # eWW.bbH/fMz before application and UID ownership.
        if uid is None:
            uid = self.allocate_uid()
            if self.event_lifecycle is not None:
                from .combat_final_modifier import NativeFinalModifier

                modifier = NativeFinalModifier(uid, 1013)
                from .combat_trigger_value_modifier import NativeRunnerAmount

                runner = NativeRunnerAmount(
                    uid, 1013, rng=self.rng, value=amount["requested"]
                )
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=amount["requested"],
                channel=2,
                final_modifier=modifier,
                runner_modifier=runner,
            )
        source = self.fight.actors[invocation.caster_id]
        target = self.fight.actors[invocation.target_id]
        minimum, maximum = _bounds(target, 97)
        result = apply_current_stat(
            family="eWQ",
            current=_current(target, 97),
            minimum=minimum,
            maximum=maximum,
            requested=amount["requested"] if runner is None else runner.value,
            percent=False,
            executable=True,
            frozen=97 in target.effect_frozen,
            source_guards_verified=True,
            limit_policy="NORMAL",
        )
        if runner is not None:
            runner.set_applied(result["actual"])

        def make_payload(value):
            payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=source.id,
                target_id=target.id,
                value=value,
                stat_id=97,
                requested=amount["requested"],
                timing_payload=context.timing_payload,
            )
            from .combat_effect_removal import _identity_fields

            messages = {}
            _identity_fields(payload, messages=messages)
            # Merge the native eWx AdditionalDatas19 room into the existing eWW fields.
            additional = (
                _integer(12, 97)
                + _integer(19, amount["room"])
                + _integer(25, amount["requested"])
            )
            from .combat_stat_effects import _varint

            old = b"\x42" + _varint(len(messages[8])) + messages[8]
            payload = payload.replace(
                old, b"\x42" + _varint(len(additional)) + additional, 1
            )
            return payload

        payload = make_payload(result["actual"])
        _write(self.fight, source.id, target, 97, result["current"])
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=target.id,
                caster_id=source.id,
                effect_class=1013,
                family="eWQ",
                stat_id=97,
                actual=result["actual"],
                limit_policy="NORMAL",
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        if runner is None or not runner.notification_suppressed:
            self.packets.append(
                (
                    13497,
                    owned_effect_application(
                        self.fight.id,
                        self.action_id,
                        effect_class=1013,
                        target_id=target.id,
                        uid=uid,
                        running_effect_payload=payload,
                    ),
                )
            )
        if context.retained and self.event_lifecycle is not None:
            register = getattr(self.event_lifecycle, "register_applied", None)
            if callable(register):
                register(effect, invocation, uid)
        if runner is not None:
            runner.finish_application()
        if self.event_lifecycle is not None:
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=result["actual"] if runner is None else runner.value,
                    channel=channel,
                    final_modifier=modifier,
                    runner_modifier=runner,
                )
        from .combat_runner_callbacks import notify_runner_value

        final_value = result["actual"] if runner is None else runner.value
        if context.retained:
            row = self.fight.owned_stat_effects[uid]
            row["actual"] = final_value
            row["payload"] = make_payload(final_value).hex()
        notify_runner_value(invocation, final_value)
        return True
