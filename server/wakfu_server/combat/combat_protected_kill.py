"""Native eZG332: add KO/death protections, set HP minimum, reset KO clock.

This runner does not infer fdy membership or dsA from the resulting HP.
"""
from dataclasses import replace

from .combat_kill import NativeKillHandler, resource_transition
from .combat_property_stack import add_property
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_effect_removal import running_effect_removal


class NativeProtectedKillHandler(NativeKillHandler):
    """Reuse exact resource snapshot/cancellation machinery, not eXc semantics."""

    def _context(self, effect, invocation):
        from .combat_stat_handler import StatExecutionContext

        if effect["effect_class"] != 332:
            raise ValueError("Wrong native eZG family")
        if (
            self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Invalid native eZG fight/caster")
        if invocation.target_id not in self.fight.actors:
            raise ValueError("Native eZG requires actual PV target authority")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native eZG execution guards")
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7:
            raise ValueError("Missing native eZG events")
        return tuple(sorted({0, *(masks[6] or ())}))

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, 332, rng=self.rng)
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
            # eZG.C is empty: no parameter or forced-context value calculation.
            self.prepared[uid] = True
            runner.set_calculated(0)
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def _apply(self, effect, invocation):
        context = self._context(effect, invocation)
        uid = invocation.native_running_uid
        if uid is not None and uid not in self.prepared:
            raise ValueError("Missing prepared native eZG runner")
        if not context.executable:
            return False
        uid = uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            runner = runner or NativeRunnerAmount(uid, 332, rng=self.rng)
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            if not self._context(effect, invocation).executable:
                return False
        actor = self.fight.actors[invocation.target_id]
        hp_before, hp_minimum, _, _ = self._snapshot(actor, 1)
        clock, minimum, raw_minimum, percent = self._snapshot(actor, 14)
        clock_after, clock_raw, clock_max = resource_transition(
            clock,
            minimum,
            raw_minimum,
            percent,
            frozen=14 in actor.effect_frozen,
            hp=False,
        )
        if 14 in actor.effect_frozen and clock_max > actor.effect_maxima[14]:
            raise ValueError("Frozen KO clock requires actual raw current authority")
        provider = getattr(self.authority, "property_counts", None)
        if not callable(provider):
            raise ValueError("Missing native eZG complete property counters")
        counts = dict(provider(self.fight, actor))
        add_property(counts, 19)
        add_property(counts, 12)
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
            effect_class=332,
            target_id=actor.id,
            uid=uid,
            running_effect_payload=payload,
        )
        # Exact c order: property additions, notification, HP minimum, KO maximum.
        actor.native_fight_property_counts = counts
        actor.native_fight_properties = frozenset(
            k for k, count in counts.items() if count
        )
        self.packets.append((12613, evaluated_application_from_observation(packet)))
        if 1 not in actor.effect_frozen:
            from .combat_hp_raw import hp_raw_present, set_hp_raw_current

            if hp_raw_present(actor):
                set_hp_raw_current(actor, actor.effect_minima[1])
            else:
                actor.hp = actor.effect_minima[1]
                actor.effect_stats[1] = actor.hp
        actor.effect_base_maxima[14] = clock_raw
        actor.effect_maxima[14] = clock_max
        actor.effect_stats[14] = clock_after
        self.fight._event(
            "protected_kill_resources",
            source_id=invocation.caster_id,
            target_id=actor.id,
            uid=uid,
            effect_class=332,
            hp=actor.hp,
            hp_before=hp_before,
            minimum=hp_minimum,
            no_ko_count=counts[19],
            no_death_count=counts[12],
            native_source="eZG.c.PV_f.PA_aZg.PA_or",
        )
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                effect_class=332,
                family="eZG",
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
            if self.event_lifecycle is not None:
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
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, 0 if runner is None else runner.value)
        return True


def remove_protected_kill(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry["family"] != "eZG" or entry["effect_class"] != 332:
        raise ValueError("Not an owned native eZG runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=332,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    # eZG inherits base removal: properties and resource writes are permanent.
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))


def registered_protected_kill(fight, actor):
    """Attest this distinct HP0 producer; caller must verify actual IN_PLAY."""
    if fight.actors.get(actor.id) is not actor or actor.hp != 0:
        return False
    from .combat_property_stack import property_present

    counts = getattr(actor, "native_fight_property_counts", None)
    if not property_present(counts, 19) or not property_present(counts, 12):
        return False
    events = getattr(fight, "events", None)
    if not isinstance(events, list):
        raise ValueError("Missing native eZG event source")
    for event in reversed(events):
        if event.get("target_id") != actor.id:
            continue
        if event.get("kind") in (
            "damage",
            "healing",
            "kill_hp_minimum_update",
            "percentage_hp_update",
        ):
            return False
        if event.get("kind") == "characteristic_changed" and event.get("stat_id") == 1:
            return False
        if event.get("kind") != "protected_kill_resources":
            continue
        return (
            event.get("native_source") == "eZG.c.PV_f.PA_aZg.PA_or"
            and event.get("effect_class") == 332
            and type(event.get("uid")) is int
            and event["uid"] > 0
            and event.get("source_id") in fight.actors
            and event.get("hp") == event.get("minimum") == 0
            and type(event.get("hp_before")) is int
            and event["hp_before"] >= 0
            and event.get("no_ko_count") == counts[19]
            and event.get("no_death_count") == counts[12]
        )
    return False
