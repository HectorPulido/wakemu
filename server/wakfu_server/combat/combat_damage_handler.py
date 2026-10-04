"""Class-agnostic eXt handler for the common effect dispatcher.

Actor snapshots and resolver decisions must be authoritative. Construct this
handler on a transaction preview; its outbox is emitted only after the whole
spell succeeds. Unsupported modes/flags fail before changing any resources.
"""
from dataclasses import dataclass, replace
from .combat_damage_parameters import (
    interpret_damage_parameters,
    interpret_damage_flags,
    damage_mastery_context,
)
from .combat_damage_healing import damage_amount, consume_damage
from .combat_effects import direct_damage


@dataclass(frozen=True)
class DamageExecutionContext:
    critical: bool
    front: bool
    blocked: bool | None
    executable: bool
    container_type: int | None
    ignore_resistance_cap: bool
    localization: str | None = None


def _snapshot(actor):
    if (
        not isinstance(actor.effect_stats, dict)
        or not isinstance(actor.effect_maxima, dict)
        or actor.effect_frozen is None
        or type(actor.physical_radius) is not int
        or actor.physical_radius < 0
    ):
        raise ValueError("Missing complete native damage actor snapshot")
    if any(type(k) is not int for k in actor.effect_frozen):
        raise ValueError("Invalid native frozen characteristics")
    if any(
        type(k) is not int or type(v) is not int for k, v in actor.effect_stats.items()
    ):
        raise ValueError("Invalid native damage characteristics")
    for identity in (92, 97, 100):
        if identity not in actor.effect_stats or actor.effect_stats[identity] < 0:
            raise ValueError("Missing native absorption characteristic")
    if (
        type(actor.effect_maxima.get(92)) is not int
        or actor.effect_maxima[92] < actor.effect_stats[92]
    ):
        raise ValueError("Missing native virtual HP maximum")
    return actor.effect_stats


class NativeDamageHandler:
    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        rng,
        block_after_calculation=None,
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng = context, rng
        self.block_after_calculation = block_after_calculation
        self.event_lifecycle = None
        self.prepared = {}

    def _calculate(self, effect, invocation):
        source = self.fight.actors.get(invocation.caster_id)
        target = self.fight.actors.get(invocation.target_id)
        if (
            source is None
            or target is None
            or target.hp <= 0
            or self.fight.phase != "active"
            or self.fight.current is None
            or effect["effect_class"] not in range(1, 6)
        ):
            raise ValueError("Invalid native damage actors or fight")
        source_stats, target_stats = _snapshot(source), _snapshot(target)
        context = self.context(effect, invocation)
        if not isinstance(context, DamageExecutionContext):
            raise ValueError("Missing native damage execution context")
        if any(
            type(v) is not bool
            for v in (
                context.critical,
                context.front,
                context.executable,
                context.ignore_resistance_cap,
            )
        ):
            raise ValueError("Unknown damage execution flags")
        if type(context.blocked) is not bool and not (
            context.blocked is None and callable(self.block_after_calculation)
        ):
            raise ValueError(
                "Native block result or post-calculation RNG callback required"
            )
        flags = effect.get("native_effect_flags")
        if flags is None or "native_localization_enabled" not in effect:
            raise ValueError("Missing exported native damage flags")
        interpreted = interpret_damage_flags(
            flags,
            container_type=context.container_type,
            executable=context.executable,
            actors_present=True,
        )
        unknown = set(interpreted["unhandled_flags"]) - {4, 5, 6, 17, 22, 23, 24}
        if unknown:
            raise ValueError(f"Unsupported native damage flags: {sorted(unknown)}")
        if not context.executable:
            return context, interpreted, None
        if context.blocked and not interpreted["block_enabled"]:
            raise ValueError("Blocked result conflicts with native effect flags")
        parameters = interpret_damage_parameters(
            effect["parameters"],
            invocation.level,
            hp_context=dict(
                source_hp=source.hp,
                source_max_hp=source.max_hp,
                target_hp=target.hp,
                target_max_hp=target.max_hp,
            ),
            rng=self.rng,
        )
        mastery = damage_mastery_context(
            flags,
            source_xy=source.position[:2],
            target_xy=target.position[:2],
            source_radius=source.physical_radius,
            target_radius=target.physical_radius,
            source_total_hp=source.hp + source_stats[92],
            source_total_max_hp=source.max_hp + source.effect_maxima[92],
        )
        amount = damage_amount(
            parameters["base"],
            effect["effect_class"],
            source_stats,
            target_stats,
            coefficient_mask=parameters["coefficient_mask"],
            rng=self.rng,
            arithmetic_context=dict(
                mastery,
                critical=context.critical,
                front=context.front if effect["native_localization_enabled"] else True,
                indirect=interpreted["indirect"],
                ignore_resistance_cap=context.ignore_resistance_cap,
                localization=context.localization
                if effect["native_localization_enabled"]
                else "FRONT",
            ),
        )
        # eXt.fOC samples BLOCK after fau arithmetic and before bbJ criteria/RNG.
        if context.blocked is None:
            blocked = self.block_after_calculation(effect, invocation)
            if type(blocked) is not bool:
                raise ValueError("Unknown native post-calculation BLOCK result")
            context = replace(context, blocked=blocked)
        return context, interpreted, amount

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=0,
            channel=1,
            blocked=False,
            localization="FRONT",
        )
        self.prepared[uid] = self._calculate(effect, invocation)
        return invocation

    def __call__(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is None:
            context, interpreted, amount = self._calculate(effect, invocation)
        else:
            if uid not in self.prepared:
                raise ValueError("Missing prepared native damage running effect")
            context, interpreted, amount = self.prepared.pop(uid)
        if amount is None:
            return False
        if uid is None:
            uid = self.allocate_uid()
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=amount,
                channel=2,
                blocked=context.blocked,
                localization=context.localization or "FRONT",
            )
        source = self.fight.actors[invocation.caster_id]
        target = self.fight.actors[invocation.target_id]
        source_stats, target_stats = _snapshot(source), _snapshot(target)
        result = consume_damage(
            amount,
            source_barrier=source_stats[100],
            target_armor=target_stats[97],
            target_virtual_hp=target_stats[92],
            target_hp=target.hp,
            blocked=context.blocked,
            bypass_armor_and_barrier=interpreted["bypass_armor_and_barrier"],
            frozen_stats=tuple(("source", k) for k in source.effect_frozen)
            + tuple(("target", k) for k in target.effect_frozen),
        )
        packet = direct_damage(
            self.fight.id,
            self.action_id,
            uid=uid,
            generic_effect=invocation.reference,
            element=effect["effect_class"],
            caster_id=source.id,
            target_id=target.id,
            damage=result["value"],
            base_uid=invocation.base_uid,
            armor_absorbed=result["armor_absorbed"],
            barrier_absorbed=result["barrier_absorbed"],
        )
        self.fight.apply_effect_damage(source.id, target.id, result["hp_loss"])
        source_stats[100] = result["source_barrier"]
        target_stats[97] = result["target_armor"]
        target_stats[92] = result["target_virtual_hp"]
        self.packets.append((12613, packet))
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=result["value"],
                channel=3,
                blocked=context.blocked,
                localization=context.localization or "FRONT",
            )
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=result["value"],
                channel=4,
                blocked=context.blocked,
                localization=context.localization or "FRONT",
            )
        return True
