"""Native eXc28 HP-minimum assignment, permanent KO-clock maximum and property."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_effect_removal import running_effect_removal
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_property_stack import add_property
from .combat_maximum_resource import effective_maximum
from .combat_actor_snapshot import native_actor_catalog


def kill_parameters(effect, level):
    count = effect.get("parameter_count")
    parameters = effect.get("parameters")
    if (
        type(count) is not int
        or count < 0
        or not isinstance(parameters, (list, tuple))
        or len(parameters) < count * 2
    ):
        raise ValueError("Missing native eXc parameter-count authority")
    return count > 0 and parameter_value(parameters, 0, level) == 1


def resource_transition(current, minimum, raw_minimum, percent, *, frozen, hp):
    """Return effective current/raw maximum/effective maximum for original setters."""
    if hp:
        return current if frozen else minimum, None, None
    row = native_actor_catalog()["characteristics"]["14"]
    raw = max(0, raw_minimum)
    maximum = effective_maximum(raw, percent, row["hard_minimum"], row["hard_maximum"])
    # fff.or clamps current to its new maximum for KO_TIME (fZB=false).
    # A frozen raw current is untouched, but aYS still clamps its effective read.
    return max(minimum, min(current, maximum)), raw, maximum


class NativeKillHandler:
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
        self.rng, self.authority, self.event_lifecycle = rng, authority, None
        self.prepared, self.runners = {}, {}

    def _context(self, effect, invocation):
        if effect["effect_class"] != 28:
            raise ValueError("Wrong native eXc family")
        if (
            self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Invalid native eXc fight/caster")
        if invocation.target_id not in self.fight.actors:
            raise ValueError("Native eXc null/nonfighter manager delivery unsupported")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native eXc execution guards")
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) < 7:
            raise ValueError("Missing native eXc events")
        return tuple(sorted({0, 192, *(masks[6] or ())}))

    def _snapshot(self, actor, stat):
        for name in (
            "effect_stats",
            "effect_minima",
            "effect_maxima",
            "effect_base_minima",
            "effect_base_maxima",
            "effect_percentages",
        ):
            values = getattr(actor, name, None)
            if not isinstance(values, dict) or type(values.get(stat)) is not int:
                raise ValueError("Missing exact native eXc characteristic snapshot")
        if not isinstance(actor.effect_frozen, frozenset):
            raise ValueError("Missing native eXc mutability")
        current, minimum = actor.effect_stats[stat], actor.effect_minima[stat]
        raw_min, raw_max, percent = (
            actor.effect_base_minima[stat],
            actor.effect_base_maxima[stat],
            actor.effect_percentages[stat],
        )
        row = native_actor_catalog()["characteristics"][str(stat)]
        maximum = effective_maximum(
            raw_max, percent, row["hard_minimum"], row["hard_maximum"]
        )
        if (
            minimum != max(row["hard_minimum"], min(row["hard_maximum"], raw_min))
            or actor.effect_maxima[stat] != maximum
            or raw_max < raw_min
            or not minimum <= current <= maximum
            or stat == 1
            and (actor.hp != current or actor.max_hp != maximum)
        ):
            raise ValueError("Inconsistent native eXc characteristic snapshot")
        return current, minimum, raw_min, percent

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, 28, rng=self.rng)
            self.runners[uid] = runner
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=1,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            self.prepared[uid] = kill_parameters(effect, invocation.level)
            # eXc.C does not write aSg or apply a context forced-value override.
            runner.set_calculated(0)
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        try:
            with self.fight.effect_resolution():
                return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        context = self._context(effect, invocation)
        uid = invocation.native_running_uid
        if uid is not None and uid not in self.prepared:
            raise ValueError("Missing prepared native eXc runner")
        suppress = (
            kill_parameters(effect, invocation.level)
            if uid is None
            else self.prepared[uid]
        )
        if not context.executable:
            return False
        uid = uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            if runner is None:
                runner = NativeRunnerAmount(uid, 28, rng=self.rng)
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            live = self._context(effect, invocation)
            if not live.executable:
                return False
            if live.retained != context.retained:
                raise ValueError("Native eXc retention changed during L2")
        actor = self.fight.actors[invocation.target_id]
        hp, hp_min, hp_raw_min, hp_percent = self._snapshot(actor, 1)
        clock, clock_min, clock_raw_min, clock_percent = self._snapshot(actor, 14)
        after, _, _ = resource_transition(
            hp, hp_min, hp_raw_min, hp_percent, frozen=1 in actor.effect_frozen, hp=True
        )
        clock_after, clock_raw, clock_max = resource_transition(
            clock,
            clock_min,
            clock_raw_min,
            clock_percent,
            frozen=14 in actor.effect_frozen,
            hp=False,
        )
        if 14 in actor.effect_frozen and clock_max > actor.effect_maxima[14]:
            raise ValueError(
                "Frozen KO clock requires actual raw current for increasing maximum"
            )
        counts = None
        if suppress:
            provider = getattr(self.authority, "property_counts", None)
            if not callable(provider):
                raise ValueError("Missing native eXc complete property counters")
            counts = dict(provider(self.fight, actor))
            add_property(counts, 65)  # Validate and precompute before mutation.
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=0,
            timing_payload=context.timing_payload,
            execution_status=0,
            executed=True,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=28,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        # Native c order: HP setter, optional permanent property, KO maximum.
        from .combat_hp_raw import hp_raw_present, set_hp_raw_current

        if hp_raw_present(actor):
            set_hp_raw_current(actor, hp_min)
        else:
            actor.hp = after
            actor.effect_stats[1] = after
        self.fight._event(
            "kill_hp_minimum_update",
            effect_class=28,
            uid=uid,
            source_id=invocation.caster_id,
            target_id=actor.id,
            hp_before=hp,
            hp=after,
            minimum=hp_min,
        )
        if hp > 0 and after == 0:
            self.fight._event("death", actor_id=actor.id)
            if hasattr(self.fight, "native_global_pv_collections"):
                from .combat_global_pv_collections import set_global_fighter_status

                set_global_fighter_status(self.fight, actor.id, "OFF_PLAY")
        if counts is not None:
            actor.native_fight_property_counts = counts
            actor.native_fight_properties = frozenset(
                k for k, value in counts.items() if value
            )
        actor.effect_base_maxima[14], actor.effect_maxima[14] = clock_raw, clock_max
        actor.effect_stats[14] = clock_after
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=28,
                family="eXc",
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
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
            death = getattr(self.event_lifecycle, "death", None)
            if hp > 0 and after == 0 and callable(death):
                death(
                    actor.id,
                    effect=effect,
                    invocation=invocation,
                    uid=uid,
                    value=runner.value,
                )
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
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, 0 if runner is None else runner.value)
        return True


def remove_kill(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry["family"] != "eXc" or entry["effect_class"] != 28:
        raise ValueError("Not an owned native eXc runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=28,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    # eXc has no bbR override: do not restore HP, KO maximum, or property65.
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
