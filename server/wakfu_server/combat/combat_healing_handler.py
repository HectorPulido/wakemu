"""Native eXs healing families on a common transaction preview.

Undead conversion, eligibility and healing-resistance guards require explicit
native context. No breed or spell whitelist; wire value is actual HP+virtual
HP healed, not the requested amount or discarded overflow.
"""
from dataclasses import dataclass, replace
from .combat_vitality_execution import (
    plan_healing_consumption,
    apply_healing_consumption,
)
from .combat_runner_target import bind_runner_target, runner_target_invocation
from .combat_damage_handler import _snapshot
from .combat_healing_parameters import (
    interpret_healing_parameters,
    healing_mastery_context,
)
from .combat_damage_healing import (
    healing_amount,
    HEAL_ELEMENTS,
)
from .combat_healing_effect import direct_healing


@dataclass(frozen=True)
class HealingExecutionContext:
    critical: bool
    executable: bool
    undead: bool
    bypass_undead: bool
    additional_mastery: int
    additional_final: int
    resistance_enabled: bool
    resistance_minimum: int
    resistance_maximum: int
    flags_verified: bool
    target_ko: bool | None = None


class NativeHealingHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, emit_events=None
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng = context, rng
        if emit_events is not None and not callable(emit_events):
            raise ValueError("Native healing event emitter must be callable")
        self.emit_events = emit_events
        self.retention = None
        self.event_lifecycle = None
        self.prepared = {}
        self.final_modifiers = {}
        self.runner_modifiers = {}

    def _calculate(self, effect, invocation, *, additional_final=0):
        from .combat_area_damage_guard import area_damage_has_no_resources

        if area_damage_has_no_resources(self.fight, invocation.target_id):
            # Verified partial area contracts have neither HP nor armor.
            # eXs.C returns before arithmetic when PV.a(ffw.sgC) is false.
            from .combat_value_transfer import apply_context_value

            amount = apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
            return None, amount
        source = self.fight.actors.get(invocation.caster_id)
        target = self.fight.actors.get(invocation.target_id)
        if (
            source is None
            or target is None
            or self.fight.phase != "active"
            or self.fight.current is None
            or effect["effect_class"] not in HEAL_ELEMENTS
        ):
            raise ValueError("Invalid native healing actors or effect")
        from .combat_runner_target_life import runner_target_life_eligible

        if not runner_target_life_eligible(
            self.fight, target, effect, invocation=invocation
        ):
            # Qe.bbJ rejects a proven corpse guard with aX(false), before L2.
            # A dead target does not need healing arithmetic descriptors. In
            # prepared execution L1 already ran; __call__ clears its caches.
            return None, None
        source_stats, target_stats = _snapshot(source), _snapshot(target)
        context = self.context(effect, invocation)
        if (
            not isinstance(context, HealingExecutionContext)
            or context.flags_verified is not True
        ):
            raise ValueError("Missing verified native healing context")
        if any(
            type(v) is not bool
            for v in (
                context.critical,
                context.executable,
                context.undead,
                context.bypass_undead,
                context.resistance_enabled,
            )
        ):
            raise ValueError("Unknown native healing flags")
        if not context.executable:
            return (context, None)
        if type(target_stats.get(32)) is not int:
            raise ValueError("Missing authoritative healing resistance")
        flags = effect.get("native_effect_flags")
        if flags is None:
            raise ValueError("Missing native healing effect flags")
        flags = frozenset(flags)
        allowed_flags = {
            2,  # DONT_USE_BLOCK: eXt HP loss, not eXs/fat HP gain.
            3,  # DONT_DISPLAY_ZONE: presentation only, not healing arithmetic.
            4,
            5,
            6,
            15,
            17,
            22,
            23,
            24,
            28,  # BYPASS_ARMOR_AND_BARRIER: eXt HP loss, not eXs HP gain.
            33,
            34,
        }
        if effect["effect_class"] == 24:
            allowed_flags.add(
                29
            )  # LIFE_STEAL_HEAL_EFFECT marker; no arithmetic consumer.
        if 8 in flags:
            # faK/faI owns rwE target ordering and the signed target cap;
            # eXs/fat healing arithmetic does not consume this flag.
            from .combat_target_ordering import validate_native_target_ordering_identity

            validate_native_target_ordering_identity(effect, invocation.reference)
            allowed_flags.add(8)
        if any(type(flag) is not int for flag in flags) or flags - allowed_flags:
            raise ValueError("Unhandled native healing flags")
        if 15 in flags:
            # eZR.bcd removes Qe.bbJ's PV.baK veto; it does not prove a
            # revival lifecycle. Ordinary authority explicitly supplies baK.
            if type(context.target_ko) is not bool:
                raise ValueError("Missing native KO healing authority")
            if context.target_ko:
                raise ValueError("Native KO healing lifecycle is not implemented")
        # eVl34 is consumed by eXt.fOG, not eXs. Undead conversion remains
        # guarded: eXs replaces PK with its synthetic definition before eXt.
        if context.bypass_undead != (33 in flags):
            raise ValueError("Undead bypass context conflicts with native flag33")
        if effect["effect_class"] == 24:
            from .combat_life_steal import life_steal_amount

            # eXv.fOC ignores the eXs mastery/final-modifier fields. It reads
            # SQ before its bonus/resistance arithmetic and replaces SQ afterward.
            amount = life_steal_amount(
                effect["parameters"],
                invocation.level,
                source_stats,
                target_stats,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
            return context, amount
        parameters = interpret_healing_parameters(
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
        mastery = healing_mastery_context(
            flags,
            source_xy=source.position[:2],
            target_xy=target.position[:2],
            source_radius=source.physical_radius,
            target_radius=target.physical_radius,
            source_total_hp=source.hp + source_stats[92],
            source_total_max_hp=source.max_hp + source.effect_maxima[92],
        )
        amount = healing_amount(
            parameters["base"],
            HEAL_ELEMENTS[effect["effect_class"]],
            source_stats,
            target_stats,
            **dict(
                mastery,
                critical=context.critical,
                coefficient_mask=parameters["coefficient_mask"],
                additional_mastery=context.additional_mastery,
                additional_final=(
                    (context.additional_final + additional_final + (1 << 31))
                    % (1 << 32)
                )
                - (1 << 31),
                rng=self.rng,
            ),
        )
        from .combat_value_transfer import apply_context_value

        amount = apply_context_value(
            amount,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return context, amount

    def prepare(self, effect, values, invocation):
        """Qe.d:L1 -> eZR.n/C arithmetic, before bbJ criteria/RNG."""
        if self.event_lifecycle is None:
            return invocation
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        from .combat_final_modifier import NativeFinalModifier

        modifier = NativeFinalModifier(uid, effect["effect_class"])
        self.final_modifiers[uid] = modifier
        from .combat_trigger_value_modifier import NativeRunnerAmount

        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        self.runner_modifiers[uid] = runner
        bind_runner_target(runner, invocation)
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=uid,
            value=0,
            channel=1,
            final_modifier=modifier,
            runner_modifier=runner,
        )
        invocation = runner_target_invocation(runner, invocation)
        self.prepared[uid] = self._calculate(
            effect, invocation, additional_final=modifier.value
        )
        return invocation

    def __call__(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is None:
            context, amount = self._calculate(effect, invocation)
        else:
            if uid not in self.prepared:
                raise ValueError("Missing native prepared healing running effect")
            context, amount = self.prepared.pop(uid)
        modifier = self.final_modifiers.pop(uid, None)
        runner = self.runner_modifiers.pop(uid, None)
        if amount is None:
            return False
        if uid is None:
            uid = self.allocate_uid()
        if runner is None:
            from .combat_trigger_value_modifier import NativeRunnerAmount

            runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        runner.set_calculated(amount)
        bind_runner_target(runner, invocation)
        invocation = runner_target_invocation(runner, invocation)
        if self.event_lifecycle is not None:
            # bbJ:L2 follows accepted criteria/probability, precedes consumption.
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=amount,
                channel=2,
                final_modifier=modifier,
                runner_modifier=runner,
            )
        amount = runner.value
        invocation = runner_target_invocation(runner, invocation)
        if context is None:
            from .combat_area_damage_guard import area_damage_has_no_resources

            if not area_damage_has_no_resources(self.fight, invocation.target_id):
                raise ValueError("Changed native partial PV healing HP authority")
            # eXs.c mu(true): retain amount/status and lifecycle, suppress PR.
            runner.notification_suppressed = True
            runner.finish_application()
            if self.event_lifecycle is not None:
                for channel in (3, 4):
                    self.event_lifecycle.phase(
                        effect,
                        invocation,
                        uid=uid,
                        value=runner.value,
                        channel=channel,
                        final_modifier=modifier,
                        runner_modifier=runner,
                    )
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
            return True
        source = self.fight.actors[invocation.caster_id]
        target = self.fight.actors[invocation.target_id]
        source_stats, target_stats = _snapshot(source), _snapshot(target)
        context = self.context(effect, invocation)
        if not context.executable:
            return False
        result = plan_healing_consumption(amount, target, target_stats, context)
        pending_retained = None
        from .combat_native_timing_context import native_definition_timing

        # eXs inherits eZR.Ty and Qe.bbR. Own the actual applied runner;
        # expiry removes that runner without reversing its healing.
        if (
            "native_execution_mode" in effect
            and native_definition_timing(effect, invocation.level)["retained"]
        ):
            if self.retention is None:
                raise ValueError("Missing retained native healing owner")
            pending_retained = self.retention.begin_healing(
                effect,
                values,
                replace(invocation, native_running_uid=uid),
                initial_value=result["value"],
            )
        packet = direct_healing(
            self.fight.id,
            self.action_id,
            uid=uid,
            generic_effect=invocation.reference,
            effect_class=effect["effect_class"],
            caster_id=source.id,
            target_id=target.id,
            restored=result["value"],
            base_uid=invocation.base_uid,
        )
        apply_healing_consumption(self.fight, source, target, result, target_stats)
        runner.set_applied(result["value"])
        if not runner.notification_suppressed:
            self.packets.append((12613, packet))
        runner.finish_application()
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=result["value"],
                channel=3,
                final_modifier=modifier,
                runner_modifier=runner,
            )
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=result["value"],
                channel=4,
                final_modifier=modifier,
                runner_modifier=runner,
            )
        elif self.emit_events is not None:
            self.emit_events(effect, invocation, packet)
        if pending_retained is not None:
            self.retention.finish_group(pending_retained, notify=False)

        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True
