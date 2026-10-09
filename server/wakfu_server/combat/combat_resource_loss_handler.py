"""Owned eVZ48/55; calculation, lifecycle, wire and secondary state are separate."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext, _bounds, _current
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_resource_loss import (
    resolve_resource_loss,
    rebase_resource_loss_application,
    apply_resource_loss,
    remove_resource_loss,
)
from .combat_effect_removal import running_effect_removal


class NativeResourceLossHandler:
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
        properties,
        secondary_state,
        event_lifecycle=None,
        delivery=None,
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.rng, self.properties, self.secondary_state = (
            rng,
            properties,
            secondary_state,
        )
        self.event_lifecycle = event_lifecycle
        self.delivery = delivery
        self.prepared = {}
        self.runner_amounts = {}

    def native_eligibility(self, effect, invocation):
        """Evaluate eZR.bcd before allocating an eVZ runner/UID."""
        if effect.get("effect_class") not in (48, 55):
            return True
        target = self.fight.actors.get(invocation.target_id)
        if target is None or target.hp > 0:
            return True
        from .combat_runner_target_life import runner_target_life_eligible

        return runner_target_life_eligible(
            self.fight, target, effect, invocation=invocation
        )

    def _calculate(self, effect, invocation):
        stat = {48: 3, 55: 2}.get(effect["effect_class"])
        if stat is None or self.fight.phase != "active":
            raise ValueError("Invalid native eVZ action or fight")
        source, target = (
            self.fight.actors.get(i)
            for i in (invocation.caster_id, invocation.target_id)
        )
        area_source = None
        if source is None:
            from .combat_state_managers import registered_area_pv

            area_source = registered_area_pv(self.fight, invocation.caster_id)
            row = getattr(self.fight, "native_effect_areas", {}).get(
                invocation.caster_id
            )
            if (
                area_source is None
                or not isinstance(row, dict)
                or row.get("native_area_contract") != "faP"
            ):
                raise ValueError("Missing native eVZ source PA presence authority")
            # faP inherits faV.a(PC)=false. eVZ.C queries that presence before
            # reading shF; the actual area supplies zero, never owner stats.
            source = area_source
        if source is None or target is None:
            raise ValueError("Native eVZ requires owned living target")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Missing native eVZ timing/guard authority")
        if target.hp <= 0:
            from .combat_runner_target_life import runner_target_life_eligible

            if not runner_target_life_eligible(
                self.fight, target, effect, invocation=invocation
            ):
                return context, stat, None, False
        flags = set(effect["native_effect_flags"])
        if flags - {1, 3, 4, 5, 6, 14, 15, 16, 17, 19, 26, 30}:
            raise ValueError("Unaudited native eVZ flags")
        if len(effect["parameters"]) < 2 or len(effect["parameters"]) % 2:
            raise ValueError("Missing native eVZ first parameter")
        requested = parameter_value(effect["parameters"], 0, invocation.level)
        if requested == -1:
            from .combat_resource_loss import triggering_resource_loss

            requested = triggering_resource_loss(
                invocation.native_trigger_context, stat
            )
        minimum, maximum = _bounds(target, stat)
        props = self.properties(target)
        if not isinstance(props, frozenset):
            raise ValueError("Missing native eVZ target property snapshot")
        executable = context.executable
        if stat == 3 and 4 in props:  # eWR/eVZ.fMy: ffe.sdB IMMOBILIZED.
            executable = False
        for actor in (target,) if area_source is not None else (source, target):
            # Exact ordinary authority attests the complete installed PA map.
            if not isinstance(self.properties(actor), frozenset) or not isinstance(
                actor.effect_stats, dict
            ):
                raise ValueError("Missing native willpower presence/value snapshot")
        plan = resolve_resource_loss(
            stat_id=stat,
            requested=requested,
            current=_current(target, stat),
            minimum=minimum,
            maximum=maximum,
            caster_willpower=0
            if area_source is not None
            else source.effect_stats.get(86, 0),
            target_willpower=target.effect_stats.get(86, 0),
            same_actor=source.id == target.id,
            ignores_willpower=30 in flags,
            frozen=stat in target.effect_frozen,
            suppresses_loss_state=19 in flags,
            random_fraction=self.rng,
            value_context=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        # eWW.bbH rejects only value0 AND eVZ.fMz current==minimum.
        executable = executable and not (
            plan.calculated == 0 and plan.before == minimum
        )
        return context, stat, plan, executable

    def prepare(self, effect, values, invocation):
        if not self.native_eligibility(effect, invocation):
            return invocation
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        from .combat_trigger_value_modifier import NativeRunnerAmount

        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        self.runner_amounts[uid] = runner
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=1,
                plan=None,
                runner_modifier=runner,
            )
        self.prepared[uid] = self._calculate(effect, invocation)
        plan = self.prepared[uid][2]
        if plan is None:
            self.prepared.pop(uid, None)
            self.runner_amounts.pop(uid, None)
            return invocation
        runner.set_calculated(plan.calculated)
        # eWR.fNa overrides Qe's PK.eg chance, rather than adding a second roll.
        # Dispatcher values are a fresh execution-local effect_profile dictionary.
        chance = (
            parameter_value(effect["parameters"], 3, invocation.level)
            if len(effect["parameters"]) >= 8
            else -1
        )
        values["probability"] = 100 if chance < 0 else max(0, min(100, chance))
        return invocation

    def __call__(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is not None and uid not in self.prepared:
            raise ValueError("Missing native prepared eVZ running effect")
        context, stat, plan, executable = (
            self._calculate(effect, invocation)
            if uid is None
            else self.prepared.pop(uid)
        )
        runner = self.runner_amounts.pop(uid, None)
        if not executable:
            return False
        if self.delivery is not None and context.retained:
            raise ValueError("Synthetic native eVZ delivery cannot retain a runner")
        uid = uid or self.allocate_uid()
        if runner is None:
            from .combat_trigger_value_modifier import NativeRunnerAmount

            runner = NativeRunnerAmount(
                uid, effect["effect_class"], rng=self.rng, value=plan.calculated
            )
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=plan.calculated,
                channel=2,
                plan=plan,
                runner_modifier=runner,
            )
        target = self.fight.actors[invocation.target_id]
        minimum, maximum = _bounds(target, stat)
        plan = rebase_resource_loss_application(
            plan,
            calculated=runner.value,
            current=_current(target, stat),
            minimum=minimum,
            maximum=maximum,
            frozen=stat in target.effect_frozen,
            suppresses_loss_state=19 in effect["native_effect_flags"],
        )
        if getattr(target, "effect_resource_raw_currents", None) is not None:
            from .combat_resource_pa_notifications import resource_shift_result, int32

            _, after, actual = resource_shift_result(
                target, stat, runner.value, subtract=True
            )
            state = (
                None
                if actual <= 0 or 19 in effect["native_effect_flags"]
                else (5227, 0, int32(actual * 10), 0, 100, 0)
            )
            plan = replace(
                plan, actual=actual, after=after, state_5227_parameters=state
            )
        secondary = None
        if plan.state_5227_parameters is not None:
            if not callable(self.secondary_state):
                raise ValueError(
                    "Native positive eVZ loss requires secondary state5227"
                )
            secondary = lambda caster, target, params, p: self.secondary_state(
                effect, invocation, uid, caster, target, params, p
            )
        runner.set_applied(plan.actual)
        apply_resource_loss(
            self.fight,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            stat_id=stat,
            plan=plan,
            secondary_state=secondary,
            after_apply=lambda *args: None,
            native_guards_verified=True,
            executable=True,
        )
        if plan.actual == 0 and plan.after == minimum:
            # eWR.d calls fRS when aSg0 and eVZ.fMz sees PA at its minimum.
            runner.notification_suppressed = True

        # eVZ.C overrides eWW.C and never assigns rCB. Fresh native Mt stays0.
        def make_payload(value):
            payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                value=value,
                stat_id=stat,
                requested=0,
                timing_payload=context.timing_payload,
                execution_status=0,
            )
            return payload

        # Synthetic native definitions have their own signed identity and wire
        # policy. Do not weaken the positive-reference codec for ordinary PKs.
        payload = None if self.delivery is not None else make_payload(plan.actual)
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=effect["effect_class"],
                family="eVZ",
                stat_id=stat,
                actual=plan.actual,
                execution_status=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        if not runner.notification_suppressed:
            if self.delivery is not None:
                self.packets.append(
                    self.delivery(effect, invocation, uid, plan.actual, context)
                )
            else:
                packet = (
                    13497,
                    owned_effect_application(
                        self.fight.id,
                        self.action_id,
                        effect_class=effect["effect_class"],
                        target_id=invocation.target_id,
                        uid=uid,
                        running_effect_payload=payload,
                    ),
                )
                if not context.retained:
                    from .combat_entity_creation_delivery import (
                        immediate_effect_application,
                    )

                    packet = immediate_effect_application(
                        self.fight.id, self.action_id, effect["effect_class"], payload
                    )
                self.packets.append(packet)
        if context.retained and self.event_lifecycle is not None:
            register = getattr(self.event_lifecycle, "register_applied", None)
            if callable(register):
                register(effect, invocation, uid)
        runner.finish_application()
        if self.event_lifecycle is not None:
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=runner.value,
                    channel=channel,
                    plan=plan,
                    runner_modifier=runner,
                )
        from .combat_runner_callbacks import notify_runner_value

        if context.retained:
            row = self.fight.owned_stat_effects[uid]
            row["actual"] = runner.value
            row["payload"] = make_payload(runner.value).hex()
        notify_runner_value(invocation, runner.value)
        return True


def remove_owned_resource_loss(stat_handler, uid):
    entry = stat_handler.fight.owned_stat_effects[uid]
    actor = stat_handler.fight.actors[entry["target_id"]]
    stat = entry["stat_id"]
    _current_before_removal = _current(actor, stat)
    minimum, maximum = _bounds(actor, stat)
    after = remove_resource_loss(
        current=_current(actor, stat),
        minimum=minimum,
        maximum=maximum,
        actual=entry["actual"],
        frozen=stat in actor.effect_frozen,
    )
    if getattr(actor, "effect_resource_raw_currents", None) is not None:
        from .combat_resource_pa_notifications import shift_resource_current

        shift_resource_current(stat_handler.fight, actor, stat, entry["actual"])
    else:
        setattr(actor, {2: "ap", 3: "mp"}[stat], after)
        actor.effect_stats[stat] = after
        from .combat_resource_pa_notifications import notify_resource_pa

        notify_resource_pa(
            stat_handler.fight, actor, stat, before_current=_current_before_removal
        )
    stat_handler.packets.append(
        (
            13560,
            running_effect_removal(
                stat_handler.fight.id,
                stat_handler.action_id,
                effect_class=entry["effect_class"],
                target_id=actor.id,
                uid=uid,
                running_effect_payload=bytes.fromhex(entry["payload"]),
            ),
        )
    )
    del stat_handler.fight.owned_stat_effects[uid]
    return True
