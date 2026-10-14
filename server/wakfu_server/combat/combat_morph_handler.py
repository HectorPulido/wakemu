"""Native eWG933 temporary spellbook application and current-book removal."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal
from .combat_morph_spellbook import (
    native_morph_profiles,
    install_morph_book,
    remove_morph_book,
)
from .combat_runner_callbacks import notify_runner_value


class NativeMorphHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, profiles=None
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context, self.rng = (
            action_id,
            allocate_uid,
            context,
            rng,
        )
        self.profiles = profiles
        self.event_lifecycle = None
        self.prepared = {}

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (tuple, list)) or len(masks) < 7:
                raise ValueError("Missing native eWG event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
            )

    def _calculate(self, effect, invocation):
        if effect.get("effect_class") != 933:
            raise ValueError("Wrong native transformation family")
        count, raw = effect["parameter_count"], effect["parameters"]
        profile = parameter_value(raw, 0, invocation.level) if count else -1
        own = count >= 2 and parameter_value(raw, 1, invocation.level) == 1
        profile = apply_context_value(
            profile,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return profile, own

    def prepare(self, effect, values, invocation):
        invocation = replace(invocation, native_running_uid=self.allocate_uid())
        runner = NativeRunnerAmount(invocation.native_running_uid, 933, rng=self.rng)
        try:
            self._phase(effect, invocation, runner, 1)
            profile, own = self._calculate(effect, invocation)
            runner.set_calculated(profile)
            self.prepared[runner.uid] = runner, own
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = replace(invocation, native_running_uid=self.allocate_uid())
        try:
            return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.retained) is not bool
            or type(context.executable) is not bool
        ):
            raise ValueError(
                "Missing native transformation execution/retention authority"
            )
        if not context.executable:
            return False
        actor = self.fight.actors.get(invocation.target_id)
        if actor is None:
            raise ValueError("Native eWG requires an actual registered eGj target")
        uid = invocation.native_running_uid
        if uid in self.prepared:
            runner, own = self.prepared[uid]
        else:
            profile, own = self._calculate(effect, invocation)
            runner = NativeRunnerAmount(uid, 933, rng=self.rng, value=profile)
            self._phase(effect, invocation, runner, 1)
        self._phase(effect, invocation, runner, 2)
        profile_id = ((runner.value + 32768) % 65536) - 32768
        profiles = native_morph_profiles() if self.profiles is None else self.profiles
        profile = profiles.get(str(profile_id))
        if profile is None:
            raise ValueError(
                "Transformation profile outside scoped native source domain"
            )
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7:
            raise ValueError("Missing native transformation subscription masks")
        # Qa.aZN excludes aZI (slot2): it removes an applied runner, never activates it.
        if any(masks[index] for index in (0, 1, 3, 4, 5)):
            raise ValueError("Subscribed transformation client execution is unproven")
        # Server actors have no client igz visual manager. dou's visual side
        # effect is represented by actual eWG delivery, not a fabricated copy.
        install_morph_book(self.fight, actor, profile, own_level=own, uid=uid)
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=actor.id,
            value=runner.value,
            timing_payload=context.timing_payload,
        )
        additional = _integer(14, int(own))  # Original il.en -> ij.mk field14.
        payload += b"\x42" + _varint(len(additional)) + additional
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                family="eWG",
                effect_class=933,
                target_id=actor.id,
                caster_id=invocation.caster_id,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        # cvX/eIK=false registers the persistent target-owned Qf runner and,
        # for this non-subscribed eWG, executes c() with its decoded value.
        # cvY/aTR only observes; it never installs the client's temporary book.
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                native_opcode=12613,
                effect_class=933,
                target_id=actor.id,
                uid=uid,
                running_effect_payload=payload,
            )
        )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        notify_runner_value(invocation, runner.value)
        return True


def remove_morph_effect(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=933,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    remove_morph_book(handler.fight, row["target_id"])
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
