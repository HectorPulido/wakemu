"""Native eWw449: distinct eHQ counters and asymmetric mapped-ffe removal."""
from dataclasses import replace
from .combat_stat_handler import StatExecutionContext
from .combat_parameters import parameter_value
from .combat_world_properties import registry
from .combat_world_property_mutation import mutate_property_manager
from .combat_stat_effects import owned_effect_payload
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_effect_removal import running_effect_removal
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value


def context_kind(fight, invocation):
    from .combat_npc_initialization import constructor_stat_context

    if constructor_stat_context(fight, invocation):
        return 3  # eGj.pGD = new eZQ(this,3).
    if fight.phase == "active" and invocation.caster_id in fight.actors:
        return 1  # fbX.fUt creates eVw; eVw.bag returns1.
    raise ValueError("Missing actual eWw PN kind authority")


def _save_world(actor, counts):
    actor.native_world_property_counts = {} if counts is None else counts
    actor.native_world_property_manager_present = counts is not None
    actor.native_world_properties = frozenset(
        k for k, v in (counts or {}).items() if v != 0
    )


class NativeWorldPropertyHandler:
    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, authority, rng
    ):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context, self.authority, self.rng = (
            allocate_uid,
            context,
            authority,
            rng,
        )
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        if effect.get("effect_class") != 449 or len(effect.get("parameters", ())) != 2:
            raise ValueError("Missing native eWw definition")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native eWw execution authority")
        return ctx

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eWw event masks")
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
        context_kind(self.fight, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 449, rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        runner.set_calculated(
            apply_context_value(
                parameter_value(effect["parameters"], 0, invocation.level),
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared[uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        ctx = self._context(effect, invocation)
        if not ctx.executable:
            self.cancel_prepared(invocation)
            return False
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.pop(invocation.native_running_uid)
        self._phase(effect, invocation, runner, 2)
        ctx = self._context(effect, invocation)
        if not ctx.executable:
            return False
        from .combat_summon_initialization import registered_or_detached_actor

        actor = registered_or_detached_actor(self.fight, invocation.target_id)
        entry = registry().get(str(runner.value))
        if actor is None or entry is None:
            return False
        native = self.authority(self.fight, actor)
        if native.targeting.get("is_eGj") is not True:
            return False
        # Preflight both namespaces before either observable mutation.
        world = self.authority.world_property_counts(self.fight, actor)
        if not isinstance(world, dict):
            raise ValueError("Missing complete native world-property counters")
        world = dict(world)
        mapped = entry["fight_property"]
        fight_counts = (
            dict(self.authority.property_counts(self.fight, actor))
            if mapped != -1
            else None
        )
        # PF UI callbacks execute in the client from the native449 application.
        if mapped != -1 and context_kind(self.fight, invocation) == 1:
            mutate_property_manager(
                fight_counts, mapped, namespace=1, applying=True, notify=lambda *_: None
            )
            actor.native_fight_property_counts = fight_counts
            actor.native_fight_properties = frozenset(
                k for k, v in fight_counts.items() if v != 0
            )
        _save_world(
            actor,
            mutate_property_manager(
                world or None,
                runner.value,
                namespace=0,
                applying=True,
                notify=lambda *_: None,
            ),
        )
        runner.finish_application()
        payload = owned_effect_payload(
            uid=runner.uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=runner.value,
            timing_payload=ctx.timing_payload,
        )
        if ctx.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                effect_class=449,
                family="eWw",
                target_id=actor.id,
                caster_id=invocation.caster_id,
                property_id=runner.value,
                fight_property=mapped,
                stat_id=None,
                actual=runner.value,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                collision_affiliation=native.targeting.get("bcN"),
                timer=None if ctx.timer is None else dict(vars(ctx.timer)),
            )
        # eWw.bbz is false: the client receives the evaluated native runner.
        observed = running_effect_removal(
            self.fight.id,
            self.action_id,
            effect_class=449,
            target_id=actor.id,
            uid=runner.uid,
            running_effect_payload=payload,
            notify_unapplication=False,
        )[:-16]
        self.packets.append(
            (
                12613,
                evaluated_application_from_observation(
                    observed, execute=not ctx.retained
                ),
            )
        )
        if ctx.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, runner.uid)
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_world_property(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row.get("effect_class") != 449 or row.get("family") != "eWw":
        raise ValueError("Missing retained native eWw identity")
    from .combat_summon_initialization import registered_or_detached_actor

    actor = registered_or_detached_actor(handler.fight, row["target_id"])
    if actor is None:
        raise ValueError("Missing actual native eWw target")
    world = getattr(actor, "native_world_property_counts", None)
    if not isinstance(world, dict):
        raise ValueError("Missing native world property counters")
    mapped = row["fight_property"]
    counts = getattr(actor, "native_fight_property_counts", None)
    if mapped != -1 and not isinstance(counts, dict):
        raise ValueError("Missing mapped native fight property counters")
    if mapped != -1:
        mutate_property_manager(
            counts, mapped, namespace=1, applying=False, notify=lambda *_: None
        )
        actor.native_fight_properties = frozenset(
            k for k, v in counts.items() if v != 0
        )
    _save_world(
        actor,
        mutate_property_manager(
            world or None,
            row["property_id"],
            namespace=0,
            applying=False,
            notify=lambda *_: None,
        ),
    )
    handler.packets.append(
        (
            13560,
            running_effect_removal(
                handler.fight.id,
                handler.action_id,
                effect_class=449,
                target_id=actor.id,
                uid=uid,
                running_effect_payload=bytes.fromhex(row["payload"]),
            ),
        )
    )
    del handler.fight.owned_stat_effects[uid]
    return True
