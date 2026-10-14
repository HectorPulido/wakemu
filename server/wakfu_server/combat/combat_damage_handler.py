"""Class-agnostic eXt handler for the common effect dispatcher.

Actor snapshots and resolver decisions must be authoritative. Construct this
handler on a transaction preview; its outbox is emitted only after the whole
spell succeeds. Unsupported modes/flags fail before changing any resources.
"""
from dataclasses import dataclass, replace
from .combat_runner_target import bind_runner_target, runner_target_invocation
from .combat_damage_parameters import (
    interpret_damage_parameters,
    interpret_damage_flags,
    damage_mastery_context,
)
from .combat_damage_healing import damage_amount, consume_damage, DAMAGE_FAMILIES
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


def _wall_target(fight, identity):
    """Resolve a registered HP-owning area without inserting it into actors."""
    row = getattr(fight, "native_effect_areas", {}).get(identity)
    if not isinstance(row, dict) or row.get("native_area_contract") not in (
        "fbd",
        "faW",
    ):
        return None
    from .combat_area_authority import area_guards
    from .combat_effect_area import native_effect_areas
    from .combat_effect_area_targets import area_targets
    from .combat_wall_area import verified_wall_constructor, wall_damage_snapshot

    definition = native_effect_areas().get(str(row.get("reference")))
    fake = row["native_area_contract"] == "faW"
    if fake:
        from .combat_fake_fighter import verified_fake_fighter
        from .combat_fake_fighter_resources import fake_fighter_damage_snapshot

        constructor = verified_fake_fighter(row, definition)
        if not constructor["characteristic_ids"]:
            return None
        snapshot = fake_fighter_damage_snapshot(row, definition)
    else:
        constructor = verified_wall_constructor(row, definition)
        snapshot = wall_damage_snapshot(row, definition)
    guards = area_guards(fight, identity)
    if guards["baG"] is not False or guards["baK"] is not False:
        raise ValueError("Native fbd damage target is not an active Qq PV")
    target = next((item for item in area_targets(fight) if item.id == identity), None)
    if target is None:
        raise ValueError("Missing registered native fbd damage target")
    return dict(
        row=row,
        constructor=constructor,
        definition=definition,
        target=target,
        snapshot=snapshot,
    )


def _apply_wall_damage(fight, source_id, wall, amount):
    """Apply eXt's PA HP change while retaining the active Qq/QI identity."""
    if type(amount) is not int or amount < 0 or source_id not in fight.actors:
        raise ValueError("Invalid native fbd damage application")
    row, constructor = wall["row"], wall["constructor"]
    from .combat_wall_area import update_wall_hp

    current = wall["snapshot"]["current_hp"]
    dealt = min(current, amount)
    after = current - dealt
    if not callable(getattr(fight, "_event", None)):
        raise ValueError("Missing native fbd damage event ledger")
    if row["native_area_contract"] == "faW":
        from .combat_fake_fighter_resources import update_fake_fighter_hp

        update_fake_fighter_hp(row, wall["definition"], after)
    else:
        update_wall_hp(row, constructor, after)
    fight._event(
        "damage", source_id=source_id, target_id=row["uid"], amount=dealt, hp=after
    )
    # fbd.baD reflects PA HP<=0, while Qq.baG/baK and Qs/QI ownership remain
    # unchanged. The native Qq.b lifecycle callback is the separate remover.
    return dealt


class NativeDamageHandler:
    native_runner_value_verified = True

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
        self.final_modifiers = {}
        self.runner_modifiers = {}
        self.retention = None

    def _damage_parameters(
        self, effect, invocation, *, source, target_hp, target_max_hp
    ):
        return interpret_damage_parameters(
            effect["parameters"],
            invocation.level,
            hp_context=dict(
                source_hp=source.hp,
                source_max_hp=source.max_hp,
                target_hp=target_hp,
                target_max_hp=target_max_hp,
            ),
            rng=self.rng,
        )

    def _context_amount(self, amount, invocation):
        from .combat_value_transfer import apply_context_value

        return apply_context_value(
            amount,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )

    def _calculate(self, effect, invocation, *, additional_final=0, runner=None):
        from .combat_native_actor_lookup import native_actor

        source = native_actor(self.fight, invocation.caster_id)
        target = native_actor(self.fight, invocation.target_id)
        if source is not None and target is None:
            from .combat_area_damage_guard import area_damage_has_no_resources

            if area_damage_has_no_resources(self.fight, invocation.target_id):
                if (
                    self.fight.phase != "active"
                    or self.fight.current is None
                    or effect["effect_class"] not in DAMAGE_FAMILIES
                ):
                    raise ValueError("Invalid native partial PV damage context")
                # eXt.C returns before arithmetic when both sgC/shQ are absent.
                return (
                    None,
                    {"native_no_resources": True},
                    0 if runner is None else runner.value,
                )
        wall = (
            None
            if target is not None
            else _wall_target(self.fight, invocation.target_id)
        )
        if (
            source is None
            or target is None
            and wall is None
            or self.fight.phase != "active"
            or self.fight.current is None
            or effect["effect_class"] not in DAMAGE_FAMILIES
        ):
            raise ValueError("Invalid native damage actors or fight")
        source_stats = _snapshot(source)
        target_stats = (
            wall["snapshot"]["stats"] if wall is not None else _snapshot(target)
        )
        target_hp = wall["snapshot"]["current_hp"] if wall is not None else target.hp
        target_max_hp = (
            wall["snapshot"]["maximum_hp"] if wall is not None else target.max_hp
        )
        target_position = (
            wall["target"].position if wall is not None else target.position
        )
        target_radius = (
            wall["target"].physical_radius
            if wall is not None
            else target.physical_radius
        )
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
        # eXt.bcd overrides eZR and always permits the KO gate. Flag15
        # (CAN_BE_EXECUTED_ON_KO) therefore adds no arithmetic or eligibility
        # change to this runner. Owned KO/revival lifecycle remains guarded.
        # eVl.rwA (3) is DONT_DISPLAY_ZONE, consumed only by aJs
        # client zone preview. eXt calculation/gates and wire remain identical.
        # eVl.rxb (31), BOMB_EFFECT, classifies the source. Native eXt has
        # no arithmetic or event override for this tag; keep it on the source.
        unknown = set(interpreted["unhandled_flags"]) - {
            3,
            4,
            5,
            6,
            15,
            17,
            22,
            23,
            24,
            31,
        }
        ordering_flags = unknown.intersection({8, 14})
        if ordering_flags:
            # faK selects faI (8) or faF (14) before the target cap.
            # The resolver supplies actual PA/XY operands; eXt owns neither sort.
            # Retain the same exported identity guard used by group runners.
            from .combat_target_ordering import validate_native_target_ordering_identity

            validate_native_target_ordering_identity(effect, invocation.reference)
            unknown.difference_update(ordering_flags)
        if unknown:
            raise ValueError(f"Unsupported native damage flags: {sorted(unknown)}")
        if not context.executable:
            return context, interpreted, None
        if wall is None:
            from .combat_runner_target_life import verify_runner_target_life

            verify_runner_target_life(self.fight, target, effect, invocation=invocation)
        if context.blocked and not interpreted["block_enabled"]:
            raise ValueError("Blocked result conflicts with native effect flags")
        parameters = self._damage_parameters(
            effect,
            invocation,
            source=source,
            target_hp=target_hp,
            target_max_hp=target_max_hp,
        )
        mastery = damage_mastery_context(
            flags,
            source_xy=source.position[:2],
            target_xy=target_position[:2],
            source_radius=source.physical_radius,
            target_radius=target_radius,
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
                additional_final=additional_final,
                additional_mastery=0 if runner is None else runner.additional_mastery,
                additional_resistance=0
                if runner is None
                else runner.additional_resistance,
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
        amount = self._context_amount(amount, invocation)
        return context, interpreted, amount

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        return self._prepare_uid(effect, values, invocation, self.allocate_uid())

    def _prepare_uid(self, effect, values, invocation, uid):
        invocation = replace(invocation, native_running_uid=uid)
        from .combat_final_modifier import NativeFinalModifier

        modifier = NativeFinalModifier(uid, effect["effect_class"])
        self.final_modifiers[uid] = modifier
        from .combat_trigger_value_modifier import NativeRunnerAmount

        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        self.runner_modifiers[uid] = runner
        bind_runner_target(runner, invocation)
        from .combat_attack_preparation import deliver_attack_preparation

        try:
            deliver_attack_preparation(
                self.event_lifecycle,
                effect,
                invocation,
                uid=uid,
                final_modifier=modifier,
                runner_modifier=runner,
            )
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                final_modifier=modifier,
                runner_modifier=runner,
                value=0,
                channel=1,
                blocked=False,
                localization="FRONT",
            )
            invocation = runner_target_invocation(runner, invocation)
            self.prepared[uid] = self._calculate(
                effect, invocation, additional_final=modifier.value, runner=runner
            )
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def prepare_activation(self, effect, values, invocation, *, clone_uid):
        # Qe.k owns this new clone UID; the original listener stays registered.
        if (
            effect.get("effect_class") != 1
            or type(clone_uid) is not int
            or not 0 < clone_uid < (1 << 63)
            or invocation.native_running_uid is not None
            or type(invocation.base_uid) is not int
            or invocation.base_uid <= 0
            or not isinstance(invocation.native_trigger_context, dict)
            or clone_uid in self.prepared
        ):
            raise ValueError("Missing audited subscribed eXt clone authority")
        listener = getattr(self.fight, "native_owned_group_effects", {}).get(
            invocation.base_uid
        )
        if (
            listener is None
            or listener.get("effect_class") != 1
            or listener.get("invocation", {}).get("reference") != invocation.reference
        ):
            raise ValueError("Missing subscribed eXt original listener")
        if self.event_lifecycle is None:
            raise ValueError("Missing subscribed eXt event lifecycle")
        return self._prepare_uid(effect, values, invocation, clone_uid)

    def cancel_prepared(self, invocation):
        uid = invocation.native_running_uid
        self.prepared.pop(uid, None)
        self.final_modifiers.pop(uid, None)
        self.runner_modifiers.pop(uid, None)

    def __call__(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is None:
            context, interpreted, amount = self._calculate(effect, invocation)
        else:
            if uid not in self.prepared:
                raise ValueError("Missing prepared native damage running effect")
            context, interpreted, amount = self.prepared.pop(uid)
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
        if callable(getattr(self, "calculated_clone_gate", None)):
            from .combat_source_split import bind_calculated_damage_clone

            invocation = replace(invocation, native_running_uid=uid)
            if not interpreted.get("native_no_resources"):
                bind_calculated_damage_clone(
                    self, effect, invocation, context, interpreted, runner, modifier
                )
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                final_modifier=modifier,
                runner_modifier=runner,
                value=amount,
                channel=2,
                blocked=False if context is None else context.blocked,
                localization="FRONT"
                if context is None
                else context.localization or "FRONT",
            )
        amount = runner.value
        invocation = runner_target_invocation(runner, invocation)
        if interpreted.get("native_no_resources"):
            from .combat_area_damage_guard import area_damage_has_no_resources

            if not area_damage_has_no_resources(self.fight, invocation.target_id):
                raise ValueError("Changed native partial PV damage resource authority")
            if "native_execution_mode" in effect:
                from .combat_native_timing_context import native_definition_timing

                if native_definition_timing(effect, invocation.level)["retained"]:
                    raise ValueError(
                        "Retained no-resource damage PV ownership is unaudited"
                    )
            # eXt.c calls mu(true): suppress PR notification, leave aSg/status
            # unchanged, and preserve the surrounding actual Qe L phases.
            runner.notification_suppressed = True
            runner.finish_application()
            if self.event_lifecycle is not None:
                for channel in (3, 4):
                    self.event_lifecycle.phase(
                        effect,
                        invocation,
                        uid=uid,
                        final_modifier=modifier,
                        runner_modifier=runner,
                        value=runner.value,
                        channel=channel,
                        blocked=False,
                        localization="FRONT",
                    )
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
            return True
        from .combat_native_actor_lookup import native_actor

        source = native_actor(self.fight, invocation.caster_id)
        target = native_actor(self.fight, invocation.target_id)
        wall = (
            None
            if target is not None
            else _wall_target(self.fight, invocation.target_id)
        )
        if target is None and wall is None:
            raise ValueError("Missing native damage target PV")
        source_stats = _snapshot(source)
        target_stats = (
            wall["snapshot"]["stats"] if wall is not None else _snapshot(target)
        )
        target_hp = wall["snapshot"]["current_hp"] if wall is not None else target.hp
        result = consume_damage(
            amount,
            source_barrier=source_stats[100],
            target_armor=target_stats.get(97, 0),
            target_virtual_hp=target_stats.get(92, 0),
            target_hp=target_hp,
            blocked=context.blocked,
            bypass_armor_and_barrier=interpreted["bypass_armor_and_barrier"],
            frozen_stats=tuple(("source", k) for k in source.effect_frozen)
            + (
                ()
                if wall is not None
                else tuple(("target", k) for k in target.effect_frozen)
            ),
        )
        pending_retained = None
        from .combat_native_timing_context import native_definition_timing

        # eXt inherits eZR.Ty and Qe.bbR (no resource reversal). Retain the
        # applied runner, not a second damage application or a fabricated stat.
        if (
            "native_execution_mode" in effect
            and native_definition_timing(effect, invocation.level)["retained"]
        ):
            if self.retention is None:
                raise ValueError("Missing retained native damage owner")
            pending_retained = self.retention.begin_damage(
                effect,
                values,
                replace(invocation, native_running_uid=uid),
                initial_value=result["value"],
            )
        packet = direct_damage(
            self.fight.id,
            self.action_id,
            uid=uid,
            generic_effect=invocation.reference,
            element=effect["effect_class"],
            caster_id=source.id,
            target_id=invocation.target_id,
            damage=result["value"],
            base_uid=invocation.base_uid,
            armor_absorbed=result["armor_absorbed"],
            barrier_absorbed=result["barrier_absorbed"],
            retained_payload=None
            if pending_retained is None
            else bytes.fromhex(pending_retained["payload"]),
        )
        if wall is None:
            from .combat_hp_raw import hp_raw_present

            self.fight.apply_effect_damage(
                source.id,
                target.id,
                result["hp_requested"] if hp_raw_present(target) else result["hp_loss"],
                native_runner_effect=effect,
                native_death_delivery=(
                    None
                    if self.event_lifecycle is None
                    or not callable(getattr(self.event_lifecycle, "death", None))
                    else lambda actor_id: self.event_lifecycle.death(
                        actor_id,
                        effect=effect,
                        invocation=invocation,
                        uid=uid,
                        value=result["value"],
                    )
                ),
            )
        else:
            _apply_wall_damage(self.fight, source.id, wall, result["hp_loss"])
        if getattr(source, "native_copy_pa_source", None) is not None:
            from .combat_copied_pa import set_copied_current

            set_copied_current(self.fight, source, 100, result["source_barrier"])
        source_stats[100] = result["source_barrier"]
        if wall is None:
            if getattr(target, "native_copy_pa_source", None) is not None:
                from .combat_copied_pa import set_copied_current

                set_copied_current(self.fight, target, 97, result["target_armor"])
                set_copied_current(self.fight, target, 92, result["target_virtual_hp"])
            target_stats[97] = result["target_armor"]
            target_stats[92] = result["target_virtual_hp"]
        runner.set_applied(result["value"])
        if not runner.notification_suppressed:
            self.packets.append((12613, packet))
        runner.finish_application()
        if wall is None and getattr(self.fight, "boss_score_profile", None) is not None:
            from wakfu_server.maps.boss_score_runtime import stage_damage

            stage_damage(
                self.fight,
                action_id=self.action_id,
                runner_uid=uid,
                source=source,
                target=target,
                result=result,
            )
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                final_modifier=modifier,
                runner_modifier=runner,
                value=result["value"],
                channel=3,
                blocked=context.blocked,
                localization=context.localization or "FRONT",
            )
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                final_modifier=modifier,
                runner_modifier=runner,
                value=result["value"],
                channel=4,
                blocked=context.blocked,
                localization=context.localization or "FRONT",
            )
        from .combat_runner_callbacks import notify_runner_value

        if pending_retained is not None:
            # Qe.d inserts the applied runner in Qf after its L3/L4 phases.
            # Store the exact eXt iN payload, including absorbed resources.
            pending_retained["payload"] = packet[19:].hex()
            self.retention.finish_group(pending_retained, notify=False)
        notify_runner_value(invocation, runner.value)
        return True
