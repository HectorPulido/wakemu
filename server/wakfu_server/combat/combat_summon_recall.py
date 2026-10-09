"""Source-backed eWz/eWA recall transition for an owned symbiot summon.

The native family clears four fight-property counters, assigns target HP to its
minimum and sets KO_TIME's raw maximum to zero. It does not call the eHU roster,
QI, fdt or global-PV removal APIs; this handler deliberately keeps those
registrations intact unless the shared HP setter's proved death transition runs.
"""
from dataclasses import replace

from .combat_kill import NativeKillHandler, resource_transition
from .combat_property_stack import remove_property
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_pr_completion import PRCompletionNotice, WakemuPRCompletionPolicy


_RECALL_PROPERTIES = (65, 66, 19, 12)


def _symbiote_owner_and_target(fight, source_id, target_id, authority):
    """Verify eWz.fNs/eWA.c's eGj/eHP and direct dpu/dpr identity checks."""
    if not callable(authority):
        raise ValueError("Missing actual native eGj/eHP recall authority")
    source = fight.actors.get(source_id)
    target = fight.actors.get(target_id)
    if source is None or target is None or source_id == target_id:
        raise ValueError("Native eWA requires actual source and target fighters")

    source_metadata = authority(fight, source)
    source_owner_id = source_metadata.targeting.get("dpu_id")
    if (
        source_metadata.targeting.get("is_eGj") is not True
        or type(source_owner_id) is not int
    ):
        raise ValueError("Native eWz source must resolve its actual eGj.dpu owner")
    owner = fight.actors.get(source_owner_id)
    if owner is None:
        raise ValueError("Native eWz eHP owner is absent from the fight")
    owner_metadata = authority(fight, owner)
    from wakfu_server.characters.captured_roster import OwnedCapturedRoster

    if (
        owner_metadata.targeting.get("is_eGj") is not True
        or owner_metadata.native_is_ehp is not True
        or not isinstance(owner_metadata.native_captured_roster, OwnedCapturedRoster)
        or owner_metadata.native_captured_roster.owner_id != owner.id
    ):
        raise ValueError(
            "Native eWA requires the owner's actual non-null eHP.drI component"
        )

    target_metadata = authority(fight, target)
    if (
        target_metadata.targeting.get("is_eGj") is not True
        or target_metadata.targeting.get("dpr_id") != owner.id
        or target_metadata.native_controller_id != owner.id
        or getattr(target, "native_controller_id", None) != owner.id
    ):
        raise ValueError("Native eWA target.dpr must be the exact source eHP owner")
    return owner, target, owner_metadata, target_metadata


class NativeSummonRecallHandler:
    """Native eWz/eWA state transition; no inferred roster or QI retirement."""

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
        authority,
        actor_authority,
        completion_policy=None
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng, self.authority = context, rng, authority
        self.actor_authority = actor_authority
        self.completion_policy = completion_policy
        self.event_lifecycle = None
        self.prepared = {}
        self.runners = {}

    def _validate(self, effect, invocation):
        if effect.get("effect_class") != 859:
            raise ValueError("Wrong native eWA family")
        if (
            self.fight.phase != "active"
            or invocation.target_id is None
            or invocation.caster_id not in self.fight.actors
            or invocation.target_id not in self.fight.actors
        ):
            raise ValueError("Native eWA requires actual active-fight actors")
        source = self.fight.actors[invocation.caster_id]
        owner, target, owner_metadata, target_metadata = _symbiote_owner_and_target(
            self.fight, source.id, invocation.target_id, self.actor_authority
        )
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Unverified native eWA execution context")
        return owner, target, owner_metadata, target_metadata, context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Missing native eWA event masks")
        return tuple(sorted({0, *(masks[6] or ())}))

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        self._validate(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 859, rng=self.rng)
        self.runners[uid] = runner
        try:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=1,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            runner.set_calculated(0)  # eWA.C is a native no-op.
            self.prepared[uid] = True
            return invocation
        except BaseException:
            self.cancel_prepared(invocation)
            raise

    def cancel_prepared(self, invocation):
        uid = invocation.native_running_uid
        self.prepared.pop(uid, None)
        self.runners.pop(uid, None)

    def __call__(self, effect, values, invocation):
        try:
            return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        owner, target, _, _, context = self._validate(effect, invocation)
        uid = invocation.native_running_uid
        if uid is not None and uid not in self.prepared:
            raise ValueError("Missing prepared native eWA runner")
        if not context.executable:
            return False
        if context.retained:
            raise ValueError(
                "Native eWA retained removal lifecycle is not source-verified"
            )
        uid = uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            if runner is None:
                runner = NativeRunnerAmount(uid, 859, rng=self.rng)
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=0,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            owner, target, _, _, live = self._validate(effect, invocation)
            if not live.executable or live.retained:
                return False

        if self.authority is None or not callable(
            getattr(self.authority, "property_counts", None)
        ):
            raise ValueError("Missing native eWA property-counter authority")
        counts = dict(self.authority.property_counts(self.fight, target))
        for property_id in _RECALL_PROPERTIES:
            remove_property(counts, property_id)
        hp, hp_min, hp_raw_min, hp_percent = NativeKillHandler._snapshot(
            None, target, 1
        )
        ko, ko_min, _, ko_percent = NativeKillHandler._snapshot(None, target, 14)
        after_hp, _, _ = resource_transition(
            hp,
            hp_min,
            hp_raw_min,
            hp_percent,
            frozen=1 in target.effect_frozen,
            hp=True,
        )
        after_ko, raw_ko, max_ko = resource_transition(
            ko, ko_min, 0, ko_percent, frozen=14 in target.effect_frozen, hp=False
        )
        if 14 in target.effect_frozen and max_ko > target.effect_maxima[14]:
            raise ValueError("Frozen KO_TIME requires its actual raw current")
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=target.id,
            value=0,
            timing_payload=context.timing_payload,
            execution_status=0,
            executed=True,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=859,
            target_id=target.id,
            uid=uid,
            running_effect_payload=payload,
        )

        # eWA.c applies properties, inherited d notification, HP minimum, KO max.
        target.native_fight_property_counts = counts
        target.native_fight_properties = frozenset(
            k for k, value in counts.items() if value
        )
        if self.completion_policy is None:
            authority = getattr(self.fight, "native_pr_completion_authority", None)
            self.completion_policy = WakemuPRCompletionPolicy(authority)
        self.completion_policy.notify(
            PRCompletionNotice(
                running_uid=uid,
                parent_uid=invocation.base_uid,
                effect_reference=invocation.reference,
                effect_class=859,
                caster_id=owner.id,
                target_id=target.id,
            )
        )
        from .combat_hp_raw import hp_raw_present, set_hp_raw_current

        if hp_raw_present(target):
            # eWA writes eGj.aZg with this exact computed setter operand; keep
            # the fresh native HP raw-current authority synchronized.
            set_hp_raw_current(target, after_hp)
        else:
            target.hp = after_hp
            target.effect_stats[1] = after_hp
        if hp > 0 and after_hp == 0:
            self.fight._event(
                "summon_recall_hp_minimum_update",
                effect_class=859,
                uid=uid,
                source_id=owner.id,
                target_id=target.id,
                hp_before=hp,
                hp=after_hp,
                minimum=hp_min,
            )
            self.fight._event("death", actor_id=target.id)
            if hasattr(self.fight, "native_global_pv_collections"):
                from .combat_global_pv_collections import set_global_fighter_status

                set_global_fighter_status(self.fight, target.id, "OFF_PLAY")
        target.effect_base_maxima[14], target.effect_maxima[14] = raw_ko, max_ko
        target.effect_stats[14] = after_ko
        self.packets.append(
            (12613, evaluated_application_from_observation(packet, execute=True))
        )
        if self.event_lifecycle is not None:
            runner.finish_application()
            death = getattr(self.event_lifecycle, "death", None)
            if hp > 0 and after_hp == 0 and callable(death):
                death(target.id, effect=effect, invocation=invocation, uid=uid, value=0)
            for channel in (3, 4):
                self.event_lifecycle.phase(
                    effect,
                    invocation,
                    uid=uid,
                    value=0,
                    channel=channel,
                    _event_ids=self._events(effect),
                    runner_modifier=runner,
                )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, 0)
        return True
