"""eYG320 capture into the actual caster eHP.drI component; no synthetic kills."""
from dataclasses import replace
from wakfu_server.characters.captured_roster import OwnedCapturedRoster
from .combat_capture_slot import add_fresh_capture
from .combat_captured_profiles import native_captured_profiles
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_property_stack import add_property
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_effect_removal import running_effect_removal
from .combat_runner_callbacks import notify_runner_value


class NativeCaptureHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, authority
    ):
        self.fight, self.packets, self.action_id = fight, packets, action_id
        self.allocate_uid, self.context, self.rng, self.authority = (
            allocate_uid,
            context,
            rng,
            authority,
        )
        self.event_lifecycle = None
        self.prepared, self.runners = {}, {}

    def _actors(self, invocation):
        caster = self.fight.actors.get(invocation.caster_id)
        target = self.fight.actors.get(invocation.target_id)
        if caster is None or target is None or self.fight.phase != "active":
            raise ValueError("Native eYG actor/source registration unsupported")
        return caster, target

    def _phase(self, effect, invocation, runner, channel):
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Missing native eYG event masks")
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
            )

    def _status(self, invocation):
        _, target = self._actors(invocation)
        metadata = self.authority(self.fight, target)
        if metadata.targeting.get("is_eGj") is not True:
            return 13
        counts = self.authority.property_counts(self.fight, target)
        return 14 if counts.get(40, 0) != 0 and counts.get(28, 0) == 0 else 13

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)
        self.runners.pop(invocation.native_running_uid, None)

    def prepare(self, effect, values, invocation):
        if effect.get("effect_class") != 320:
            raise ValueError("Wrong native capture family")
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 320, rng=self.rng)
        self.runners[uid] = runner
        try:
            self._phase(effect, invocation, runner, 1)
            self.prepared[uid] = self._status(invocation)
            runner.set_calculated(
                apply_context_value(
                    0,
                    None
                    if invocation.native_context_hex is None
                    else bytes.fromhex(invocation.native_context_hex),
                )
            )
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        try:
            return self._apply(effect, invocation)
        finally:
            self.cancel_prepared(invocation)

    def _apply(self, effect, invocation):
        if effect.get("effect_class") != 320:
            raise ValueError("Wrong native capture family")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native capture guards")
        if not context.executable:
            return False
        uid = invocation.native_running_uid
        runner, status = self.runners[uid], self.prepared[uid]
        self._phase(effect, invocation, runner, 2)
        live = self.context(effect, invocation)
        if live.source_guards_verified is not True or live.retained != context.retained:
            raise ValueError("Native capture guards changed during L2")
        if not live.executable:
            return False
        caster, target = self._actors(invocation)
        amount = runner.value
        if status == 14:
            source = self.authority(self.fight, caster)
            target_source = self.authority(self.fight, target)
            if (
                source.targeting.get("is_eGj") is not True
                or source.native_is_ehp is not True
            ):
                return False
            record = getattr(self.fight, "native_captured_rosters", {}).get(
                str(caster.id)
            )
            roster = (
                OwnedCapturedRoster.from_record(record, expected_owner_id=caster.id)
                if record is not None
                else source.native_captured_roster
            )
            if (
                not isinstance(roster, OwnedCapturedRoster)
                or roster.owner_id != caster.id
            ):
                raise ValueError("Missing actual hydrated eHP.drI capture component")
            if (
                target_source.native_actor_type is None
                or type(target_source.targeting.get("dTE")) is not bool
            ):
                raise ValueError("Missing original capture target type/dTE authority")
            if target_source.native_actor_type != 1 or target_source.targeting["dTE"]:
                return False
            profile = native_captured_profiles().get(str(target_source.breed_id))
            if profile is not None:
                amount, new_roster = add_fresh_capture(roster, profile)
                if amount == -1:
                    return False
                fight_counts = dict(self.authority.property_counts(self.fight, target))
                provider = getattr(self.authority, "world_property_counts", None)
                if not callable(provider):
                    raise ValueError(
                        "Missing complete native capture world-property counters"
                    )
                world_counts = dict(provider(self.fight, target))
                for identity in (19, 12, 66, 65):
                    add_property(fight_counts, identity)
                add_property(world_counts, 28)
                # Validate payload before committing any component/property mutation.
                owned_effect_payload(
                    uid=uid,
                    base_uid=invocation.base_uid,
                    generic_effect=invocation.reference,
                    caster_id=caster.id,
                    target_id=target.id,
                    value=amount,
                    timing_payload=context.timing_payload,
                    execution_status=status,
                    executed=True,
                )
                records = dict(getattr(self.fight, "native_captured_rosters", {}))
                updates = dict(
                    getattr(self.fight, "native_captured_roster_updates", {})
                )
                records[str(caster.id)] = updates[
                    str(caster.id)
                ] = new_roster.to_record()
                (
                    self.fight.native_captured_rosters,
                    self.fight.native_captured_roster_updates,
                ) = (records, updates)
                target.native_fight_property_counts = fight_counts
                target.native_fight_properties = frozenset(
                    k for k, v in fight_counts.items() if v != 0
                )
                target.native_world_property_counts = world_counts
                target.native_world_properties = frozenset(
                    k for k, v in world_counts.items() if v != 0
                )
                runner.set_calculated(amount)
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=caster.id,
            target_id=target.id,
            value=amount,
            timing_payload=context.timing_payload,
            execution_status=status,
            executed=True,
        )
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                family="eYG",
                effect_class=320,
                target_id=target.id,
                caster_id=caster.id,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        if context.retained:
            self.packets.append(
                (
                    13497,
                    owned_effect_application(
                        self.fight.id,
                        self.action_id,
                        effect_class=320,
                        target_id=target.id,
                        uid=uid,
                        running_effect_payload=payload,
                    ),
                )
            )
        else:
            from .combat_entity_creation_delivery import immediate_effect_application

            self.packets.append(
                immediate_effect_application(
                    self.fight.id, self.action_id, 320, payload
                )
            )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        notify_runner_value(invocation, runner.value)
        return True


def remove_capture(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row["effect_class"] != 320 or row["family"] != "eYG":
        raise ValueError("Not a retained native capture runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=320,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
