"""Native eWM250: caster maximum percentage and actual target HP PA."""
from .combat_maximum_resource import NativeMaximumResourceHandler, _snapshot, _int32
from .combat_stat_handler import StatExecutionContext
from .combat_parameters import parameter_value
from .combat_summon_initialization import registered_or_detached_actor
from .combat_npc_initialization import constructor_stat_context
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_effects import _integer, _varint
from .combat_effect_removal import running_effect_removal


def hp_operand(fight, identity):
    if identity is None:
        return None
    actor = registered_or_detached_actor(fight, identity)
    if actor is not None:
        if 1 not in actor.effect_stats:
            raise ValueError("Missing actual native eWM fighter HP presence")
        current, raw, maximum, minimum, raw_min, percent, low, high = _snapshot(
            actor, 1
        )
        return dict(
            actor=actor,
            current=current,
            raw_maximum=raw,
            maximum=maximum,
            minimum=minimum,
            raw_minimum=raw_min,
            percentage=percent,
            frozen=1 in actor.effect_frozen,
        )
    from .combat_state_managers import registered_area_pv

    if registered_area_pv(fight, identity) is None:
        raise ValueError("Missing actual native eWM PV identity")
    from .combat_area_damage_guard import area_damage_has_no_resources

    if area_damage_has_no_resources(fight, identity):
        return None
    from .combat_damage_handler import _wall_target

    area = _wall_target(fight, identity)
    if area is None:
        raise ValueError("Missing actual native eWM area HP PA")
    if area["row"]["native_area_contract"] == "faW":
        from .combat_fake_fighter_resources import fake_fighter_hp_state

        state = fake_fighter_hp_state(area["row"], area["definition"])
        key = "native_faw_hp_current"
    else:
        from .combat_wall_area import wall_hp_state

        state = wall_hp_state(area["row"], area["constructor"])
        key = "native_wall_hp_current"
    return dict(state, area=area, current_key=key)


def _maximum(operand, requested):
    if "actor" in operand:
        actor = operand["actor"]
        from .combat_hp_raw import hp_raw_present, set_hp_raw_maximum

        if not hp_raw_present(actor):
            raise ValueError("Missing native eWM raw HP current authority")
        set_hp_raw_maximum(actor, requested)
    else:
        from .combat_area_hp_pa import set_area_hp_maximum

        set_area_hp_maximum(
            operand["area"]["row"],
            {k: v for k, v in operand.items() if k not in ("area", "current_key")},
            requested,
            operand["current_key"],
        )


def _shift(operand, amount, *, subtract=False):
    if "actor" in operand:
        from .combat_hp_raw import shift_hp_raw_current

        shift_hp_raw_current(operand["actor"], amount, subtract=subtract)
    else:
        from .combat_area_hp_pa import shift_area_hp_current

        shift_area_hp_current(
            operand["area"]["row"],
            {k: v for k, v in operand.items() if k not in ("area", "current_key")},
            amount,
            operand["current_key"],
            subtract=subtract,
        )


class NativeCasterHPMaximumHandler(NativeMaximumResourceHandler):
    def _context(self, effect, invocation):
        if effect.get("effect_class") != 250 or len(effect.get("parameters", ())) != 6:
            raise ValueError("Unsupported native eWM definition")
        if self.fight.phase != "active" and not constructor_stat_context(
            self.fight, invocation
        ):
            raise ValueError("Invalid native eWM fight context")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eWM guards")
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7:
            raise ValueError("Missing native eWM masks")
        return tuple(sorted({0, *(masks[6] or ())}))

    def _calculate(self, effect, invocation):
        context = self._context(effect, invocation)
        percentage, apply_current, remove_current = [
            parameter_value(effect["parameters"], i, invocation.level) for i in range(3)
        ]
        source = hp_operand(self.fight, invocation.caster_id)
        uid = invocation.native_running_uid
        runner = self.runner_amounts.get(uid)
        amount = 0 if runner is None else runner.value
        if source is not None:
            product = _int32(percentage * source["maximum"])
            amount = (abs(product) // 100) * (-1 if product < 0 else 1)
        from .combat_value_transfer import apply_context_value

        amount = apply_context_value(
            amount,
            None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        return context, amount, bool(apply_current), bool(remove_current)

    def _apply(self, effect, values, invocation):
        uid = invocation.native_running_uid
        if uid is None:
            context, amount, apply_current, remove_current = self._calculate(
                effect, invocation
            )
        else:
            if uid not in self.prepared_maxima:
                raise ValueError("Missing prepared native eWM runner")
            context, amount, apply_current, remove_current = self.prepared_maxima.pop(
                uid
            )
        if not context.executable:
            return False
        from .combat_trigger_value_modifier import NativeRunnerAmount

        uid = uid or self.allocate_uid()
        runner = self.runner_amounts.get(uid)
        if self.event_lifecycle is not None:
            runner = runner or NativeRunnerAmount(uid, 250, rng=self.rng, value=amount)
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=runner.value,
                channel=2,
                _event_ids=self._events(effect),
                runner_modifier=runner,
            )
            live = self._context(effect, invocation)
            if not live.executable:
                return False
            if context.retained != live.retained:
                raise ValueError("Native eWM retention changed during L2")
        amount = amount if runner is None else runner.value
        operand = hp_operand(self.fight, invocation.target_id)
        if operand is None:
            return False
        # Require raw-current authority before changing either PA component.
        if "actor" in operand:
            from .combat_hp_raw import hp_raw_present, hp_raw_current

            if not hp_raw_present(operand["actor"]):
                raise ValueError("Missing native eWM raw HP current authority")
            hp_raw_current(operand["actor"])
        before_raw, before_max = operand["raw_maximum"], operand["maximum"]
        if before_raw != (1 << 31) - 1:
            _maximum(operand, _int32(before_raw + amount))
        operand = hp_operand(self.fight, invocation.target_id)
        actual, effective_delta = (
            _int32(operand["raw_maximum"] - before_raw),
            _int32(operand["maximum"] - before_max),
        )
        if apply_current:
            _shift(operand, effective_delta)
        if runner is not None:
            runner.set_applied(actual)

        def payload_for(value):
            payload = owned_effect_payload(
                uid=uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                value=value,
                timing_payload=context.timing_payload,
            )
            additional = (
                _integer(31, int(apply_current))
                + _integer(32, int(remove_current))
                + _integer(10, effective_delta)
            )
            return payload + b"\x42" + _varint(len(additional)) + additional

        payload = payload_for(actual)
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=250,
                family="eWM",
                stat_id=1,
                actual=actual,
                effective_delta=effective_delta,
                reversible=apply_current,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        if runner is None or not runner.notification_suppressed:
            packet = owned_effect_application(
                self.fight.id,
                self.action_id,
                effect_class=250,
                target_id=invocation.target_id,
                uid=uid,
                running_effect_payload=payload,
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
        if runner is not None:
            runner.finish_application()
        if self.event_lifecycle is not None:
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
        final = actual if runner is None else runner.value
        if context.retained:
            self.fight.owned_stat_effects[uid].update(
                actual=final, payload=payload_for(final).hex()
            )
        from .combat_runner_callbacks import notify_runner_value

        notify_runner_value(invocation, final)
        return True


def remove_caster_hp_maximum(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry.get("family") != "eWM" or entry.get("effect_class") != 250:
        raise ValueError("Missing native eWM removal identity")
    operand = hp_operand(handler.fight, entry["target_id"])
    if entry["reversible"] and operand is not None:
        if operand["current"] > 0:
            delta = entry["effective_delta"]
            _shift(
                operand,
                operand["current"] - 1 if delta > operand["current"] else delta,
                subtract=True,
            )
        operand = hp_operand(handler.fight, entry["target_id"])
        if operand["raw_maximum"] != (1 << 31) - 1:
            _maximum(operand, _int32(operand["raw_maximum"] - entry["actual"]))
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=250,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    handler.packets.append((13560, packet))
    del handler.fight.owned_stat_effects[uid]
    return True
