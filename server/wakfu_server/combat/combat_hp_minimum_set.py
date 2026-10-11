"""Native eXw830: PA.aZg on actual present HP, without KO-clock mutation."""
from dataclasses import replace
from .combat_kill import NativeKillHandler
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_stat_effects import owned_effect_payload, owned_effect_application
from .combat_observation_delivery import evaluated_application_from_observation
from .combat_effect_removal import running_effect_removal


class NativeHPMinimumSetHandler(NativeKillHandler):
    """Reuse owned runner infrastructure; eXw has its own setter semantics."""

    def _context(self, effect, invocation):
        if effect.get("effect_class") != 830 or self.fight.phase != "active":
            raise ValueError("Invalid native eXw family/fight")
        if (
            invocation.caster_id is not None
            and invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Missing actual native eXw source PV")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing native eXw execution guards")
        return context

    def _events(self, effect):
        masks = effect.get("target_masks")
        if not isinstance(masks, (tuple, list)) or len(masks) != 7:
            raise ValueError("Missing native eXw event masks")
        return tuple(sorted({0, *(masks[6] or ())}))

    def _target(self, identity):
        if identity is None:
            return None
        actor = self.fight.actors.get(identity)
        if actor is not None:
            if not isinstance(actor.effect_stats, dict):
                raise ValueError("Missing actual native eXw HP presence")
            if 1 not in actor.effect_stats:
                raise ValueError("Missing actual native fighter HP presence authority")
            current, minimum, _, _ = self._snapshot(actor, 1)
            return dict(actor=actor, current=current, minimum=minimum)
        from .combat_state_managers import registered_area_pv

        if registered_area_pv(self.fight, identity) is None:
            raise ValueError("Missing actual native eXw target PV")
        from .combat_area_damage_guard import area_damage_has_no_resources

        if area_damage_has_no_resources(self.fight, identity):
            return None
        from .combat_damage_handler import _wall_target

        area = _wall_target(self.fight, identity)
        if area is None:
            raise ValueError("Missing native eXw area HP authority")
        return dict(
            area=area,
            current=area["snapshot"]["current_hp"],
            minimum=area["snapshot"]["minima"][1],
        )

    def prepare(self, effect, values, invocation):
        if self.event_lifecycle is None:
            return invocation
        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            runner = NativeRunnerAmount(uid, 830, rng=self.rng)
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
            self.prepared[uid] = True
            # Native C is empty: preserve the actual L1 mutable running value.
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def _apply(self, effect, invocation):
        context = self._context(effect, invocation)
        uid = invocation.native_running_uid
        if uid is not None and uid not in self.prepared:
            raise ValueError("Missing prepared native eXw runner")
        if not context.executable:
            return False
        uid = uid or self.allocate_uid()
        runner = self.runners.get(uid)
        if self.event_lifecycle is not None:
            runner = runner or NativeRunnerAmount(uid, 830, rng=self.rng)
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
            if live.retained != context.retained:
                raise ValueError("Native eXw retention changed during L2")
        target = self._target(invocation.target_id)
        if target is None:
            return False  # Native mu(true): null PV or absent HP cannot execute.
        payload = owned_effect_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=invocation.target_id,
            value=0 if runner is None else runner.value,
            timing_payload=context.timing_payload,
            execution_status=0,
            executed=True,
        )
        packet = owned_effect_application(
            self.fight.id,
            self.action_id,
            effect_class=830,
            target_id=invocation.target_id,
            uid=uid,
            running_effect_payload=payload,
        )
        actor = target.get("actor")
        if actor is not None:
            from .combat_hp_raw import hp_raw_present, set_hp_raw_current

            if hp_raw_present(actor):
                set_hp_raw_current(actor, target["minimum"])
            elif 1 not in actor.effect_frozen:
                actor.hp = actor.effect_stats[1] = target["minimum"]
            after = actor.hp
        else:
            area = target["area"]
            if area["row"]["native_area_contract"] == "faW":
                from .combat_fake_fighter_resources import update_fake_fighter_hp

                updated_hp = update_fake_fighter_hp(
                    area["row"], area["definition"], target["minimum"]
                )
            else:
                from .combat_wall_area import update_wall_hp

                updated_hp = update_wall_hp(
                    area["row"], area["constructor"], target["minimum"]
                )
            after = updated_hp["current"]
        self.fight._event(
            "hp_minimum_update",
            effect_class=830,
            uid=uid,
            source_id=invocation.caster_id,
            target_id=invocation.target_id,
            hp_before=target["current"],
            hp=after,
            minimum=target["minimum"],
        )
        died = actor is not None and target["current"] > 0 and after == 0
        if died:
            self.fight._event("death", actor_id=actor.id)
            if hasattr(self.fight, "native_global_pv_collections"):
                from .combat_global_pv_collections import set_global_fighter_status

                set_global_fighter_status(self.fight, actor.id, "OFF_PLAY")
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                target_id=invocation.target_id,
                caster_id=invocation.caster_id,
                effect_class=830,
                family="eXw",
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
            if died and callable(death):
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


def remove_hp_minimum_set(handler, uid):
    entry = handler.fight.owned_stat_effects[uid]
    if entry.get("family") != "eXw" or entry.get("effect_class") != 830:
        raise ValueError("Not an owned native eXw runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=830,
        target_id=entry["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(entry["payload"]),
    )
    del handler.fight.owned_stat_effects[
        uid
    ]  # No native bbR override: never restore HP.
    handler.packets.append((13560, packet))
