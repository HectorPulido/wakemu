"""Native eXx/eXy job-manager modifiers, independent of combat characteristics.

Applied Qf rows are the durable modifier ledger. Removing a row reverses its
additive eRM contribution without touching HP/AP/MP or combat stat dictionaries.
"""
from dataclasses import replace

from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_effect_removal import running_effect_removal
from .combat_observation_delivery import evaluated_application_from_observation

# eVi constructors select both eRJ kind and native job action kind.
FAMILIES = {
    2000: ("plant_probability", (2,)),
    2001: ("collect_quantity", (3,)),
    2002: ("craft_speed", (8,)),
    2003: ("plant_speed", (2,)),
    2004: ("collect_speed", (3,)),
    2005: ("xp", (2, 3, 8)),
    2006: ("xp", (8,)),
    2007: ("xp", (2,)),
    2008: ("xp", (3,)),
}


def manager_value(fight, target_id, kind, profession_id, action_kind):
    """eRM.fF: the global action entry plus the matching profession entry."""
    return sum(
        row["actual"]
        for row in fight.owned_stat_effects.values()
        if row.get("family") in ("eXx", "eXy")
        and row["target_id"] == target_id
        and row["modifier_kind"] == kind
        and row["profession_id"] in (0, profession_id)
        and action_kind in row["action_kinds"]
    )


class NativeProfessionHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, authority, rng
    ):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context = allocate_uid, context
        self.authority, self.rng = authority, rng
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        if effect.get("effect_class") not in FAMILIES or len(
            effect.get("parameters", ())
        ) not in (2, 4):
            raise ValueError("Unsupported native job modifier definition")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Missing native profession modifier execution authority")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (tuple, list)) or len(masks) != 7:
                raise ValueError("Missing native job modifier event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                runner_modifier=runner,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
            )

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        runner.set_calculated(
            parameter_value(effect["parameters"], 0, invocation.level)
        )
        self.prepared[uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        context = self._context(effect, invocation)
        if not context.executable:
            self.cancel_prepared(invocation)
            return False
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.pop(invocation.native_running_uid)
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable:
            return False
        from .combat_summon_initialization import registered_or_detached_actor

        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        if actor is None:
            return False
        if self.authority(self.fight, actor).targeting.get("is_eGj") is not True:
            return False
        if not context.retained:
            raise ValueError("Native job modifier requires retained Qf ownership")
        scope = (
            0
            if len(effect["parameters"]) == 2
            else parameter_value(effect["parameters"], 1, invocation.level)
        )
        kind, action_kinds = FAMILIES[effect["effect_class"]]
        runner.finish_application()
        payload = owned_effect_payload(
            uid=runner.uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=runner.value,
            timing_payload=context.timing_payload,
        )
        self.fight.owned_stat_effects[runner.uid] = dict(
            uid=runner.uid,
            effect_class=effect["effect_class"],
            family="eXy" if effect["effect_class"] == 2005 else "eXx",
            target_id=actor.id,
            caster_id=invocation.caster_id,
            modifier_kind=kind,
            action_kinds=list(action_kinds),
            profession_id=scope,
            stat_id=None,
            actual=runner.value,
            payload=payload.hex(),
            state_uid=invocation.state_uid,
            timer=None if context.timer is None else dict(vars(context.timer)),
        )
        observed = running_effect_removal(
            self.fight.id,
            self.action_id,
            effect_class=effect["effect_class"],
            target_id=actor.id,
            uid=runner.uid,
            running_effect_payload=payload,
        )[:-16]
        self.packets.append(
            (12613, evaluated_application_from_observation(observed, execute=False))
        )
        if self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, runner.uid)
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_profession(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if (
        row.get("family") not in ("eXx", "eXy")
        or row.get("effect_class") not in FAMILIES
    ):
        raise ValueError("Missing owned native profession modifier")
    handler.packets.append(
        (
            13560,
            running_effect_removal(
                handler.fight.id,
                handler.action_id,
                effect_class=row["effect_class"],
                target_id=row["target_id"],
                uid=uid,
                running_effect_payload=bytes.fromhex(row["payload"]),
            ),
        )
    )
    del handler.fight.owned_stat_effects[uid]
    return True
