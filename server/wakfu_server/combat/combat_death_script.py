"""Native eWE1099: retained death-presentation script assignment and reset."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_effect_removal import running_effect_removal


class NativeDeathScriptHandler:
    native_runner_value_verified = True

    def __init__(self, fight, packets, *, action_id, allocate_uid, context, rng):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.rng, self.event_lifecycle = rng, None
        self.prepared, self.runners = {}, {}

    def _context(self, effect, invocation):
        if effect["effect_class"] != 1099 or len(effect["parameters"]) < 2:
            raise ValueError("Unsupported native eWE definition")
        from .combat_npc_initialization import constructor_stat_context
        from .combat_summon_initialization import registered_or_detached_actor

        constructor = constructor_stat_context(self.fight, invocation)
        if (
            self.fight.phase != "active" and not constructor
        ) or registered_or_detached_actor(self.fight, invocation.caster_id) is None:
            raise ValueError("Invalid native eWE fight/caster")
        if registered_or_detached_actor(self.fight, invocation.target_id) is None:
            # Non-eGj PV is a native no-op, but area retention/delivery has its
            # own manager contract. Do not fabricate an actor or silent success.
            raise ValueError("Native eWE non-fighter/null-target delivery unsupported")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native eWE execution guards")
        # eWE.bcd is true: there is no independent living-target restriction.
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native eWE events")
        return tuple(sorted({0, *(masks[6] or ())}))

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        self._context(effect, invocation)
        events = self._events(effect)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, 1099, rng=self.rng)
            self.runners[uid] = runner
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=1,
                _event_ids=events,
                runner_modifier=runner,
            )
            # Original eWE.C reads only parameter0; it does not call eZR.n.
            amount = parameter_value(effect["parameters"], 0, invocation.level)
            self.prepared[uid] = amount
            runner.set_calculated(amount)
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        try:
            return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        context = self._context(effect, invocation)
        uid = invocation.native_running_uid
        if uid is None:
            amount = parameter_value(effect["parameters"], 0, invocation.level)
        else:
            if uid not in self.prepared:
                raise ValueError("Missing prepared native eWE runner")
            amount = self.prepared[uid]
        if not context.executable:
            return False
        uid = uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            if runner is None:
                runner = NativeRunnerAmount(uid, 1099, rng=self.rng, value=amount)
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=amount,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            live = self._context(effect, invocation)
            if not live.executable:
                return False
            if live.retained != context.retained:
                raise ValueError("Native eWE retention changed during L2")
            amount = runner.value
        from .combat_summon_initialization import registered_or_detached_actor

        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        actor.native_death_script_id = amount

        def payload_for(value):
            return owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=actor.id,
                value=value,
                timing_payload=context.timing_payload,
                execution_status=0,
                executed=True,
            )

        payload = payload_for(amount)
        actor.native_immediate_death_script = (
            None
            if context.retained
            else {
                "producer": "eWE.c.eGj.PI",
                "fight_id": self.fight.id,
                "actor_id": actor.id,
                "caster_id": invocation.caster_id,
                "uid": uid,
                "reference": invocation.reference,
                "value": amount,
                "payload_hex": payload.hex(),
            }
        )
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=1099,
                family="eWE",
                stat_id=None,
                actual=amount,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=1099,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        # Immediate eWE applies its decoded PI operand through aVo's evaluated
        # execution path. Retained runners keep the native Qf registration path.
        self.packets.append(
            (
                12613,
                evaluated_application_from_observation(
                    packet, execute=not context.retained
                ),
            )
        )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        if self.event_lifecycle is not None:
            runner.finish_application()
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=runner.value,
                    channel=channel,
                    _event_ids=self._events(effect),
                    runner_modifier=runner,
                )
        final = amount if runner is None else runner.value
        if context.retained:
            entry = self.fight.owned_stat_effects[uid]
            entry["actual"], entry["payload"] = final, payload_for(final).hex()
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, final)
        return True


def remove_death_script(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry["effect_class"] != 1099 or entry["family"] != "eWE":
        raise ValueError("Not a native retained death-script runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=1099,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    from .combat_summon_initialization import registered_or_detached_actor

    actor = registered_or_detached_actor(handler.fight, entry["target_id"])
    if actor is None:
        raise ValueError("Missing owned eWE removal actor")
    # Native bbR never restores the previous script or recomputes an overlay.
    actor.native_death_script_id = -1
    actor.native_immediate_death_script = None
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
