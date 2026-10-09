"""Native446/eXZ clears complete fight-property counter; removal never restores it."""
from dataclasses import replace
from .combat_value_transfer import apply_context_value
from .combat_parameters import parameter_value
from .combat_fight_property import property_registry
from .combat_property_stack import clear_property
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_effect_removal import running_effect_removal


class NativeFightPropertyClearHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, authority
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.authority = authority
        self.rng, self.event_lifecycle = rng, None
        self.prepared, self.runners = {}, {}

    def _context(self, effect, invocation):
        if effect["effect_class"] != 446:
            raise ValueError("Unsupported native eXZ definition")
        if (
            self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Invalid native eXZ fight/caster")
        if invocation.target_id not in self.fight.actors:
            # Non-eGj PV is a native no-op, but area retention/delivery has its
            # own manager contract. Do not fabricate an actor or silent success.
            raise ValueError("Native eXZ non-fighter/null-target delivery unsupported")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native eXZ execution guards")
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native eXZ events")
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
            runner = NativeRunnerAmount(uid, 446, rng=self.rng)
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
            # eXZ.C reads parameter0; inherited eZR.n then applies PS context.
            amount = apply_context_value(
                parameter_value(effect["parameters"], 0, invocation.level),
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
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
            amount = apply_context_value(
                parameter_value(effect["parameters"], 0, invocation.level),
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        else:
            if uid not in self.prepared:
                raise ValueError("Missing prepared native eXZ runner")
            amount = self.prepared[uid]
        if not context.executable:
            return False
        uid = uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            if runner is None:
                runner = NativeRunnerAmount(uid, 446, rng=self.rng, value=amount)
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
                raise ValueError("Native eXZ retention changed during L2")
            amount = runner.value
        actor = self.fight.actors[invocation.target_id]
        if amount not in property_registry():
            return False  # eXZ.c calls mu(true) after ffe.Ua returns null.
        counts_provider = getattr(self.authority, "property_counts", None)
        if not callable(counts_provider):
            raise ValueError("Missing complete native PB property counts")
        counts = dict(counts_provider(self.fight, actor))
        # eGj.h first removes PL containers carrying matching eXI. No current
        # implemented producer installs eXI; reject an actual such owned row.
        if any(
            row.get("family") == "eXI"
            and row.get("target_id") == actor.id
            and row.get("property_id") == amount
            for row in self.fight.owned_stat_effects.values()
        ):
            raise ValueError("Native eXI collateral PL removal provider unavailable")

        def payload_for(value):
            return owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=actor.id,
                value=value,
                timing_payload=context.timing_payload,
                execution_status=-1,
                executed=True,
            )

        payload = payload_for(amount)
        clear_property(counts, amount)
        actor.native_fight_property_counts = counts
        actor.native_fight_properties = frozenset(
            key for key, value in counts.items() if value != 0
        )
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=446,
                family="eXZ",
                stat_id=None,
                actual=amount,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=446,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        self.packets.append((12613, evaluated_application_from_observation(packet)))
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


def remove_fight_property_clear(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry["effect_class"] != 446 or entry["family"] != "eXZ":
        raise ValueError("Not a native retained property-clear runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=446,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    # Inherited eZR.bbR does not restore the cleared native property.
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
