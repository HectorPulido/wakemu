"""eYV1030 changes actual bcM affiliation and restores its saved signed byte."""
from dataclasses import replace
from .combat_parameters import parameter_value
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_value_transfer import apply_context_value
from .combat_stat_handler import StatExecutionContext
from .combat_stat_effects import owned_effect_payload, owned_effect_delivery
from .combat_effect_removal import running_effect_removal


def signed_affiliation(value):
    if type(value) is not int or not -(1 << 31) <= value < (1 << 31):
        raise ValueError("Missing native eYV signed amount")
    return ((value + 128) % 256) - 128


class NativeAffiliationHandler:
    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, authority
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng, self.authority = context, rng, authority
        self.event_lifecycle, self.prepared = None, {}

    def _context(self, effect, invocation):
        if (
            effect["effect_class"] != 1030
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Native eYV requires an active fighter caster")
        actor_target = self.fight.actors.get(invocation.target_id)
        area_target = None
        if actor_target is None:
            area_target = getattr(self.fight, "native_effect_areas", {}).get(
                invocation.target_id
            )
            if area_target is None:
                raise ValueError("Native eYV requires an actual fighter or area PV")
            from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
            from .combat_area_affiliation import area_affiliation

            identity = invocation.target_id
            if (
                type(identity) is not int
                or area_target.get("uid") != identity
                or area_target.get("native_area_contract")
                not in SUPPORTED_AREA_CONTRACTS
                or area_target.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
            ):
                raise ValueError("Native eYV requires a registered native area PV")
            manager = area_target.get("native_running_effect_manager")
            if type(manager) is not bool:
                raise ValueError("Missing native eYV area Qf authority")
            from .combat_state_ledger import StateLedger

            ledger = area_target.get("state_ledger")
            if manager:
                if not isinstance(ledger, StateLedger) or ledger.actor_id != identity:
                    raise ValueError("Missing actual native eYV area Qf")
            elif ledger is not None:
                raise ValueError("Native eYV area without Qf has an invented ledger")
            area_affiliation(self.fight, area_target)
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eYV execution authority")
        if (
            area_target is not None
            and area_target["native_running_effect_manager"] is False
            and context.retained
        ):
            # Native faV.bax only supplies Qf when its constructor has the
            # running-effect-manager property. Do not retain on a null-Qf PV.
            context = replace(context, retained=False)
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eYV event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
            )

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 1030, rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        amount = parameter_value(effect["parameters"], 0, invocation.level)
        runner.set_calculated(
            apply_context_value(
                amount,
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
        context = self._context(effect, invocation)
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.pop(invocation.native_running_uid, None)
        if runner is None:
            raise ValueError("Missing prepared native eYV runner")
        if not context.executable:
            return False
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable or runner.value == -1:
            return False
        actor = self.fight.actors.get(invocation.target_id)
        area_target = None
        if actor is not None:
            if self.authority(self.fight, actor).targeting.get("is_amO") is not True:
                return False
            old = getattr(actor, "native_fight_affiliation", actor.team)
            target_id = actor.id
        else:
            from .combat_area_affiliation import area_affiliation

            area_target = getattr(self.fight, "native_effect_areas", {}).get(
                invocation.target_id
            )
            if area_target is None or area_target.get("uid") != invocation.target_id:
                raise ValueError("Native eYV area target disappeared before apply")
            old = area_affiliation(self.fight, area_target)
            target_id = invocation.target_id
        if type(old) is not int or not -128 <= old < 128:
            raise ValueError("Missing actual saved eYV bcM affiliation")
        affiliation = signed_affiliation(runner.value)
        if area_target is None:
            actor.native_fight_affiliation = affiliation
        else:
            area_target["native_fight_affiliation"] = affiliation
        if area_target is None and hasattr(self.fight, "native_controller_registry"):
            from .combat_controller_registry import set_native_current_team

            set_native_current_team(
                self.fight, actor.id, actor.native_fight_affiliation
            )

        def payload_for(value):
            return owned_effect_payload(
                uid=runner.uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=target_id,
                value=value,
                timing_payload=context.timing_payload,
            )

        payload = payload_for(runner.value)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                target_id=target_id,
                caster_id=invocation.caster_id,
                effect_class=1030,
                family="eYV",
                stat_id=None,
                actual=runner.value,
                saved_affiliation=old,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        self.packets.append(
            owned_effect_delivery(
                self.fight.id,
                self.action_id,
                effect_class=1030,
                target_id=target_id,
                uid=runner.uid,
                running_effect_payload=payload,
            )
        )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, runner.uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        if context.retained:
            row = self.fight.owned_stat_effects[runner.uid]
            row["actual"], row["payload"] = (
                runner.value,
                payload_for(runner.value).hex(),
            )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, runner.value)
        return True


def remove_affiliation(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row["family"] != "eYV":
        raise ValueError("Not an owned native affiliation effect")
    actor = handler.fight.actors.get(row["target_id"])
    area_target = None
    if actor is None:
        area_target = getattr(handler.fight, "native_effect_areas", {}).get(
            row["target_id"]
        )
        if area_target is None:
            area_target = getattr(
                handler.fight, "native_retired_area_managers", {}
            ).get(row["target_id"])
        if area_target is None or area_target.get("uid") != row["target_id"]:
            raise ValueError("Missing current eYV fighter or registered area PV")
        from .combat_area_contracts import SUPPORTED_AREA_CONTRACTS
        from .combat_area_affiliation import area_affiliation
        from .combat_state_ledger import StateLedger

        if (
            area_target.get("native_area_contract") not in SUPPORTED_AREA_CONTRACTS
            or area_target.get("native_fight_affiliation_source") != "faV.j(PV).bcM"
            or area_target.get("native_running_effect_manager") is not True
        ):
            raise ValueError("Missing retained native eYV area Qf authority")
        ledger = area_target.get("state_ledger")
        if not isinstance(ledger, StateLedger) or ledger.actor_id != row["target_id"]:
            raise ValueError("Missing retained native eYV area Qf")

        area_affiliation(handler.fight, area_target)
    old = row["saved_affiliation"]
    if type(old) is not int or not -128 <= old < 128:
        raise ValueError("Missing saved native affiliation")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=1030,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    if area_target is None:
        actor.native_fight_affiliation = old
    else:
        area_target["native_fight_affiliation"] = old
    if area_target is None and hasattr(handler.fight, "native_controller_registry"):
        from .combat_controller_registry import set_native_current_team

        set_native_current_team(handler.fight, actor.id, old)
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
