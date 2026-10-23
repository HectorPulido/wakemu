"""Audited eXE/eYg/eZi delayed runners through owned Qf and callbacks."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
from dataclasses import replace
from .combat_native_delay_queue import enqueue, deliver, cancel, validate

_SCOPE = ContextVar("native_Tu_execution", default=None)
SUPPORTED = frozenset({321, 330, 400})


def scope_for(effect):
    current = _SCOPE.get()
    return current if current is not None and current["effect"] is effect else None


@contextmanager
def timing_scope(effect, mode, uid=None, *, preflight_accepted=False):
    if (
        mode not in ("registration", "delivery")
        or effect["effect_class"] not in SUPPORTED
    ):
        raise ValueError("Unaudited delayed runner scope")
    if (
        type(preflight_accepted) is not bool
        or preflight_accepted
        and mode != "delivery"
    ):
        raise ValueError("Invalid delayed preflight authority")
    token = _SCOPE.set(
        dict(effect=effect, mode=mode, uid=uid, preflight_accepted=preflight_accepted)
    )
    try:
        yield
    finally:
        _SCOPE.reset(token)


class NativeDelayedEffects:
    def __init__(self, dispatcher, retention, lifecycle):
        if (
            retention is None
            or getattr(dispatcher, "native_clone_authority", None) is None
        ):
            raise ValueError(
                "Delayed Qe requires complete ordinary lifecycle authority"
            )
        if lifecycle is None or not callable(getattr(lifecycle, "phase", None)):
            raise ValueError("Delayed Qe requires ordinary L1/L2 source producer")
        self.lifecycle = lifecycle
        self.dispatcher, self.retention, self.fight = (
            dispatcher,
            retention,
            retention.fight,
        )
        validate(self.fight.native_delay_queue)

    def _phase(self, effect, invocation, *, uid, value, channel):
        # eXE/eYg inherit the generic Qe event mask. OrdinaryHealingEvents
        # also hosts generic Qe delivery, which must receive that exact mask
        # explicitly instead of selecting elemental eXs healing events.
        masks = effect.get("target_masks")
        if (
            not isinstance(masks, (tuple, list))
            or len(masks) != 7
            or masks[6] is not None
            and (
                not isinstance(masks[6], (tuple, list))
                or any(type(event) is not int for event in masks[6])
            )
        ):
            raise ValueError("Missing actual delayed Qe native event mask")
        events = tuple(sorted({0, *(masks[6] or ())}))
        return self.lifecycle.phase(
            effect, invocation, uid=uid, value=value, channel=channel, _event_ids=events
        )

    def schedule(self, effect, values, invocation):
        from .combat_parameters import _float32, _integer as java_integer
        import math
        from .combat_native_timing_context import native_definition_timing

        if scope_for(effect) is not None or effect.get("native_execution_mode") != 2:
            return False
        fields = effect.get("native_timing_definition")
        if not isinstance(fields, dict):
            raise ValueError("Missing actual eVv.eo timing authority")
        product = _float32(_float32(fields["ryI"]) * invocation.level)
        delta = (
            java_integer(math.floor(product))
            if math.isfinite(product)
            else java_integer(product)
        )
        delay = ((fields["ryH"] + delta + 32768) % 65536) - 32768
        if delay <= 0:
            return False  # Tt.biU => eZR.bbW false; ordinary immediate path.
        if effect["effect_class"] not in SUPPORTED:
            raise ValueError("Delayed native runner calculation is not implemented")
        if self.retention.is_subscription(effect, invocation):
            raise ValueError(
                "Delayed subscription requires its separate native producer"
            )
        fields = effect["native_timing_definition"]
        if any(
            type(fields.get(k)) is not bool
            for k in ("clock_on_caster", "clock_on_target", "esr")
        ):
            raise ValueError("Missing actual delayed clock routing")
        caster, target = invocation.caster_id, invocation.target_id
        clock = (
            caster
            if fields["clock_on_caster"] and caster is not None
            else target
            if fields["clock_on_target"] and target is not None
            else target
            if target is not None
            else caster
        )
        if (
            type(clock) is not int
            or clock not in self.fight.actors
            or self.fight.current is None
        ):
            raise ValueError("Missing actual delayed clock actor")
        # Capture PL before returning from the native fyW child traversal.
        initial_value = 0
        if effect["effect_class"] == 321:
            handler = self.dispatcher._operation_handler(321)
            invocation, initial_value = handler.prepare_delayed(
                effect, values, invocation
            )
            invocation = replace(
                invocation, native_delayed_uid=invocation.native_running_uid
            )
        with timing_scope(effect, "registration"):
            timing = native_definition_timing(effect, invocation.level)
            pending = self.retention.begin_group(
                effect, values, invocation, initial_value=initial_value
            )
        if pending is None or pending.get("native_null_qf"):
            raise ValueError("Delayed runner lacks actual Qf registration")
        uid = pending["uid"]
        pending["native_delayed"] = True
        if effect["effect_class"] == 321:
            pending["native_delayed_value"] = initial_value
        else:
            self._phase(effect, invocation, uid=uid, value=0, channel=1)
        with timing_scope(effect, "registration", uid):
            self.retention.finish_group(pending)
        order = tuple(self.fight.order)
        clock_index = order.index(clock) if clock in order else -1
        enqueue(
            self.fight.native_delay_queue,
            uid=uid,
            clock_id=clock,
            delay=timing["delay"],
            expire_at_end=fields["esr"],
            current_round=self.fight.native_timeline_round,
            on_clock_turn=self.fight.current.id == clock,
            clock_not_reached=clock_index < 0 or clock_index > self.fight.turn_index,
            invocation=deepcopy(
                self.fight.native_owned_group_effects[uid]["invocation"]
            ),
        )
        from .combat_pending_restoration import annotate_scheduled_restoration

        annotate_scheduled_restoration(self.fight, self.dispatcher.effects, uid)
        return True

    def boundary(self, *, actor_id, round_number, phase, round_cleanup=False):
        from .combat_effect_dispatch import EffectInvocation

        # Real Qf removal cancels handles. Old/inconsistent handles never execute.
        queue = self.fight.native_delay_queue
        for row in tuple(queue["entries"]):
            if row["uid"] not in self.fight.native_owned_group_effects:
                cancel(queue, row["uid"])

        def execute(row):
            uid = row["uid"]
            pending = self.fight.native_owned_group_effects.get(uid)
            if (
                pending is None
                or pending.get("native_delayed") is not True
                or pending["invocation"] != row["invocation"]
            ):
                raise ValueError("Missing exact retained delayed Qe authority")
            invocation = EffectInvocation(**pending["invocation"])
            effect = self.dispatcher.effects[str(invocation.reference)]
            if effect["effect_class"] not in SUPPORTED:
                raise ValueError("Unaudited delayed Qe family")
            # eYg/eXE override bcd=true; both inherit eZR.fNd=false.
            # Read the installed policy and actual eGj type, never infer baw
            # from HP or reuse event-copy i(source) as delayed bbH authority.
            from .combat_ordinary_death import corpse_gate_bypassed
            from .combat_native_actor_lookup import native_actor
            from .combat_random_earth_damage import native_child_context
            from .combat_native_criterion_failure import (
                evaluate_native_effect_condition,
            )
            from .combat_definitions import effect_profile

            if effect["effect_class"] == 321:
                eligible = self.dispatcher._operation_handler(321).native_eligibility(
                    effect, invocation
                )
                if not eligible:
                    self.retention.remove_group(uid)
                    return False
            elif not corpse_gate_bypassed(
                effect, fight=self.fight, invocation=invocation
            ):
                raise ValueError(
                    "Delayed runner requires its installed constant bcd policy"
                )
            if invocation.target_id is not None:
                actor = native_actor(self.fight, invocation.target_id)
                if actor is None:
                    raise ValueError("Delayed recipient lacks actual eGj.baw producer")
                authority = self.lifecycle.adapter.actor_authority(self.fight, actor)
                if authority.targeting.get("is_eGj") is not True:
                    raise ValueError("Delayed recipient lacks actual eGj.baw producer")
            bypass_probability, bypass_criteria, cancelled = native_child_context(
                invocation
            )
            accepted = (
                not cancelled
                and effect["minimum_level"]
                <= invocation.level
                <= effect["maximum_level"]
            )
            if accepted and not bypass_criteria:
                accepted = evaluate_native_effect_condition(
                    effect["criteria"], self.dispatcher.condition_context(invocation)
                )
            if accepted and not bypass_probability:
                values = effect_profile(effect, invocation.level)
                accepted = self.dispatcher.probability_accepts(
                    values["probability"], invocation
                )
                if type(accepted) is not bool:
                    raise ValueError(
                        "Delayed probability requires authoritative decision"
                    )
            if not accepted:
                self.retention.remove_group(uid)
                return False
            if effect["effect_class"] == 330:
                self._phase(effect, invocation, uid=uid, value=0, channel=2)
                if uid not in self.fight.native_owned_group_effects:
                    return False
            # A delayed group is already in Qf while its children run. Keep
            # that actual row so removing its state can synchronously remove
            # the runner; never re-register it after owner removal.
            if effect["effect_class"] == 400:
                del self.fight.native_owned_group_effects[uid]
                del self.fight.native_retained_records[uid]
                self.fight.native_retained_order.remove(uid)
            invocation = replace(invocation, native_delayed_uid=uid)
            with timing_scope(effect, "delivery", uid, preflight_accepted=True):
                result = self.dispatcher.execute(invocation)
                if effect["effect_class"] == 330:
                    for channel in (3, 4):
                        self._phase(
                            effect, invocation, uid=uid, value=0, channel=channel
                        )
                    from .combat_native_timing_context import native_definition_timing

                    if (
                        uid in self.fight.native_owned_group_effects
                        and not native_definition_timing(effect, invocation.level)[
                            "retained"
                        ]
                    ):
                        self.retention.remove_group(uid)
                return result

        return deliver(
            queue,
            clock_id=actor_id,
            round_number=round_number,
            phase=phase,
            round_cleanup=round_cleanup,
            execute=execute,
        )
