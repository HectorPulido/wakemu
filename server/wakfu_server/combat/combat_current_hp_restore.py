"""Source-proven eXO196 calculation and additional data, without a runner route."""
from .combat_effects import _integer
from .combat_parameters import parameter_value
from .combat_resource_loss import stochastic_native_round
from wakfu_server.equipment_damage import _float


def restore_parameters(parameters, level, *, parameter_count=None):
    """Fresh eXO.C; private flags are not serialized as running amounts."""
    if not isinstance(parameters, (list, tuple)) or len(parameters) % 2:
        raise ValueError("Unsupported native eXO parameter definition")
    count = len(parameters) // 2 if parameter_count is None else parameter_count
    if type(count) is not int or count < 0 or count * 2 > len(parameters):
        raise ValueError("Missing native eXO parameter count")
    values = [
        parameter_value(parameters, index, level) for index in range(min(count, 4))
    ]
    return dict(
        percentage_mode=bool(values),
        percentage=values[0] if values else 0,
        initial_amount=0 if values else 1,
        require_original_controller=len(values) > 1 and values[1] == 1,
        restore_virtual_hp=len(values) > 2 and values[2] == 1,
        restore_ap_mp=len(values) > 3 and values[3] == 1,
    )


def restored_percentage_amount(maximum, percentage, *, random_fraction=None):
    """eXO.fPy computes max(1, UP.bt(float32(max)/100*percentage))."""
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in (maximum, percentage)
    ):
        raise ValueError("Missing actual native eXO maximum/percentage")
    value = _float(_float(_float(maximum) / _float(100)) * _float(percentage))
    return max(1, stochastic_native_round(value, random_fraction))


def restore_additional(virtual_hp_amount, restore_virtual_hp, restore_ap_mp):
    """eXO.b(iP): il.ek/int10, il.r/bool17, il.s/bool18, including false."""
    if (
        type(virtual_hp_amount) is not int
        or not -(1 << 31) <= virtual_hp_amount < (1 << 31)
        or type(restore_virtual_hp) is not bool
        or type(restore_ap_mp) is not bool
    ):
        raise ValueError("Missing native eXO additional calculation")
    return (
        _integer(10, virtual_hp_amount)
        + _integer(17, int(restore_virtual_hp))
        + _integer(18, int(restore_ap_mp))
    )


class NativeCurrentHPRestoreHandler:
    """Fresh eXO resource assignment; unproved triggered strategy routes reject."""

    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, rng, authority
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng, self.authority = context, rng, authority
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        from .combat_stat_handler import StatExecutionContext

        if (
            effect["effect_class"] != 196
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
            or invocation.target_id not in self.fight.actors
        ):
            raise ValueError("Native eXO requires actual fighter source and target")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eXO execution authority")
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Missing native eXO event masks")
        return tuple(sorted({1, 202, *(masks[6] or ())}))

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )

    def prepare(self, effect, values, invocation):
        from dataclasses import replace
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_value_transfer import apply_context_value

        self._context(effect, invocation)
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 196, rng=self.rng)
        try:
            self._phase(effect, invocation, runner, 1)
            count = effect.get("parameter_count")
            if type(count) is not int:
                raise ValueError("Missing actual native eXO parameter count")
            parameters = restore_parameters(
                effect["parameters"], invocation.level, parameter_count=count
            )
            amount = apply_context_value(
                parameters["initial_amount"],
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
            runner.set_calculated(amount)
            self.prepared[uid] = (runner, parameters)
        except BaseException:
            self.prepared.pop(uid, None)
            raise
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        from .combat_property_stack import property_present
        from .combat_stat_handler import _current, _bounds
        from .combat_actor_snapshot import native_actor_catalog
        from .combat_stat_effects import owned_effect_payload, owned_effect_application
        from .combat_observation_delivery import evaluated_application_from_observation
        from .combat_effects import _varint
        from .combat_runner_callbacks import notify_runner_value

        context = self._context(effect, invocation)
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        pair = self.prepared.pop(invocation.native_running_uid, None)
        if pair is None:
            raise ValueError("Missing prepared native eXO runner")
        runner, parameters = pair
        if not context.executable:
            return False
        target = self.fight.actors[invocation.target_id]
        self._phase(effect, invocation, runner, 2)
        context = self._context(effect, invocation)
        if not context.executable:
            return False
        counts = self.authority.property_counts(self.fight, target)
        if parameters["require_original_controller"]:
            controller = self.authority(self.fight, target).native_controller_id
            if controller is None:
                raise ValueError("Missing actual eXO original controller")
            from .combat_global_pv_collections import global_fighter_guards

            if not global_fighter_guards(self.fight, controller)["baF"]:
                return False
        if 1 not in target.effect_stats or property_present(counts, 66):
            return False
        from .combat_restore_strategy import (
            triggered_restore_requested,
            mark_restored_strategy,
        )

        restore_strategy = triggered_restore_requested(
            invocation.native_trigger_context
        )
        if restore_strategy:
            # Preflight before PA writes; the actual assignment is sequenced
            # below after HP/virtual HP, matching eXO.c.
            strategy = getattr(target, "native_restore_strategy", None)
            if (
                not isinstance(strategy, dict)
                or strategy.get("source") != "fresh.eGz.pHO"
                or type(strategy.get("restored")) is not bool
            ):
                raise ValueError("Missing actual eGz restore strategy component")
        virtual = 0
        if parameters["percentage_mode"]:
            runner.set_calculated(
                restored_percentage_amount(
                    target.effect_maxima[1],
                    parameters["percentage"],
                    random_fraction=self.rng,
                )
            )
            if 92 in target.effect_stats:
                virtual = restored_percentage_amount(
                    target.effect_maxima[92],
                    parameters["percentage"],
                    random_fraction=self.rng,
                )
        writes = {1: runner.value}
        if parameters["restore_virtual_hp"] and 92 in target.effect_stats:
            writes[92] = virtual
        if parameters["restore_ap_mp"]:
            writes.update(
                {
                    stat: target.effect_maxima[stat]
                    for stat in (2, 3)
                    if stat in target.effect_stats
                }
            )
        calculated = {}
        for stat, requested in writes.items():
            current = _current(target, stat)
            minimum, maximum = _bounds(target, stat)
            definition = native_actor_catalog()["characteristics"][str(stat)]
            from .combat_hp_raw import hp_raw_present

            if (
                definition["expandable"]
                and requested > maximum
                and getattr(target, "native_copy_pa_source", None) is None
                and not (stat == 1 and hp_raw_present(target))
            ):
                raise ValueError("Native eXO expandable raw current authority required")
            calculated[stat] = (
                current
                if stat in target.effect_frozen
                else max(minimum, min(maximum, requested))
            )
        # eXO writes PA directly, without inventing damage/heal events.
        strategy_written = False
        for stat, after in calculated.items():
            if stat in (2, 3) and restore_strategy and not strategy_written:
                mark_restored_strategy(target)
                strategy_written = True
            if getattr(target, "native_copy_pa_source", None) is not None:
                from .combat_copied_pa import set_copied_current

                set_copied_current(self.fight, target, stat, writes[stat])
                continue
            if stat == 1:
                from .combat_hp_raw import hp_raw_present, set_hp_raw_current

                if hp_raw_present(target):
                    set_hp_raw_current(target, writes[stat])
                    continue
            if (
                stat in (2, 3)
                and getattr(target, "effect_resource_raw_currents", None) is not None
            ):
                from .combat_resource_pa_notifications import set_resource_current

                set_resource_current(self.fight, target, stat, writes[stat])
                continue
            before_current = target.effect_stats[stat]
            target.effect_stats[stat] = after
            if stat == 1:
                target.hp = after
            elif stat == 2:
                target.ap = after
            elif stat == 3:
                target.mp = after
            from .combat_resource_pa_notifications import notify_resource_pa

            notify_resource_pa(self.fight, target, stat, before_current=before_current)
        if restore_strategy and not strategy_written:
            mark_restored_strategy(target)

        def payload_for(amount):
            payload = owned_effect_payload(
                uid=runner.uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=target.id,
                value=amount,
                timing_payload=context.timing_payload,
            )
            additional = restore_additional(
                virtual, parameters["restore_virtual_hp"], parameters["restore_ap_mp"]
            )
            return payload + b"\x42" + _varint(len(additional)) + additional

        payload = payload_for(runner.value)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid] = dict(
                uid=runner.uid,
                target_id=target.id,
                caster_id=invocation.caster_id,
                effect_class=196,
                family="eXO",
                stat_id=None,
                actual=runner.value,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        application = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=196,
            target_id=target.id,
            uid=runner.uid,
            running_effect_payload=payload,
        )
        self.packets.append(
            (
                12613,
                evaluated_application_from_observation(
                    application, execute=not context.retained
                ),
            )
        )
        if context.retained and self.event_lifecycle is not None:
            self.event_lifecycle.register_applied(effect, invocation, runner.uid)
        runner.finish_application()
        for channel in (3, 4):
            self._phase(effect, invocation, runner, channel)
        if context.retained:
            self.fight.owned_stat_effects[runner.uid]["actual"] = runner.value
            self.fight.owned_stat_effects[runner.uid]["payload"] = payload_for(
                runner.value
            ).hex()
        notify_runner_value(invocation, runner.value)
        return True


def remove_current_hp_restore(handler, uid):
    """eXO inherits eZR.d: removal does not reverse assigned resources."""
    from .combat_effect_removal import running_effect_removal

    row = handler.fight.owned_stat_effects[uid]
    if row["family"] != "eXO":
        raise ValueError("Not an owned native eXO runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=196,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
