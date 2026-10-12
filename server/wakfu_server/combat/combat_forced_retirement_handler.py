"""Native eXl934: inherited eZR packets and exact fighter retirement domain."""


class NativeForcedRetirementHandler:
    """Installed zero-parameter eXl runner with owned eGj.dnu application."""

    native_runner_value_verified = True

    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        retention,
        rng,
        actor_authority=None,
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.retention, self.rng = context, retention, rng
        self.actor_authority = actor_authority
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        from .combat_stat_handler import StatExecutionContext

        if effect.get("effect_class") != 934 or self.fight.phase != "active":
            raise ValueError("Missing actual native eXl family/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError(
                "Missing actual native forced-retirement execution authority"
            )
        if invocation.target_id is None:
            return context  # Installed c returns before inherited d on null bfs.
        from .combat_state_managers import state_manager

        if state_manager(self.fight, invocation.target_id) is None:
            raise ValueError("Unregistered native eXl PV recipient")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eXl event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
                _execution_status=-1,
                _nullable_target=True,
            )

    def prepare(self, effect, values, invocation):
        from dataclasses import replace
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_value_transfer import apply_context_value

        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 934, rng=self.rng)
        self.prepared[uid] = runner
        try:
            self._phase(effect, invocation, runner, 1)
            # eXl.C is empty. Only inherited eZR.n context forcing writes aSg.
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

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        runner = self.prepared.get(invocation.native_running_uid)
        if runner is None:
            raise ValueError("Missing prepared native eXl runner")
        try:
            context = self._context(effect, invocation)
            if not context.executable or invocation.target_id is None:
                return False
            self._phase(effect, invocation, runner, 2)
            from .combat_forced_retirement import (
                NativeForcedRetirementCleanup,
                force_retire_fighter,
            )

            actor = self.fight.actors.get(invocation.target_id)
            if actor is None:
                raise ValueError("Missing registered native eGj retirement recipient")
            cleanup = NativeForcedRetirementCleanup(self.retention)
            from .combat_retained_runtime import group_payload
            from .combat_stat_effects import owned_effect_application
            from .combat_effects import _integer, _varint
            from wakfu_server.wire import proto_fields

            owner, owner_id = self.retention.container(invocation)
            if not isinstance(context.timing_payload, bytes):
                raise ValueError("Missing actual native eXl TimeDatas")
            # Current status is inherited -1; executed becomes true during c.
            clock = b"".join(
                _integer(tag >> 3, value)
                if tag & 7 == 0
                else _varint(tag) + _varint(len(value)) + value
                for tag, value in proto_fields(context.timing_payload)
                if tag >> 3 not in (2, 5)
            )
            clock += _integer(2, -1) + _integer(5, 1)
            payload = group_payload(
                uid=runner.uid,
                base_uid=invocation.base_uid,
                generic_effect=invocation.reference,
                caster_id=invocation.caster_id,
                target_id=invocation.target_id,
                cell=invocation.cell,
                container_type=owner["container_type"],
                container_id=owner_id,
                timing_payload=clock,
                context_payload=None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
                initial_value=runner.value,
            )
            packet = owned_effect_application(
                self.fight.id,
                self.action_id,
                effect_class=934,
                target_id=invocation.target_id,
                uid=runner.uid,
                running_effect_payload=payload,
            )
            force_retire_fighter(
                self.fight,
                actor,
                uid=runner.uid,
                cleanup=cleanup,
                property_counts=getattr(self.actor_authority, "property_counts", None),
            )
            self.packets.append((13497, packet))
            if context.retained:
                self.fight.owned_stat_effects[runner.uid] = dict(
                    uid=runner.uid,
                    effect_class=934,
                    family="eXl",
                    caster_id=invocation.caster_id,
                    target_id=invocation.target_id,
                    actual=0,
                    stat_id=None,
                    payload=payload.hex(),
                    state_uid=invocation.state_uid,
                    timer=None if context.timer is None else dict(vars(context.timer)),
                )
                self.retention.register_applied_stat(effect, invocation, runner.uid)
            runner.finish_application()
            self._phase(effect, invocation, runner, 3)
            self._phase(effect, invocation, runner, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, runner.value)
            return True
        finally:
            self.cancel_prepared(invocation)


def remove_forced_retirement_runner(handler, uid):
    """Inherited runner removal never restores a retired fighter."""
    from .combat_effect_removal import running_effect_removal

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != "eXl" or row.get("effect_class") != 934:
        raise ValueError("Missing owned native eXl runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=934,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
