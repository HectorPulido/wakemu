"""eZF316 snapshots one PV's Qf and removes only eVi.rtZ/rua runners."""
from .combat_retained_effects import NativeRetainedEffectView, NativeRetainedRemoval


AURA_RUNNER_FAMILIES = frozenset((314, 338))


def aura_removal_snapshot(view, target_id):
    """Capture native Qf order before bbN mutates any selected runner."""
    if not isinstance(view, NativeRetainedEffectView):
        raise ValueError("Missing complete native aura runner population")
    if type(target_id) is not int or target_id == 0:
        raise ValueError("Missing native aura removal PV recipient")
    # Native central insertion order preserves each owning Qf's subsequence.
    # bfs is the recipient; a serialized effect target can differ from bfv.
    return tuple(
        entry.uid
        for entry in view.entries
        if entry.manager_id == target_id and entry.effect_class in AURA_RUNNER_FAMILIES
    )


def remove_native_auras(view, removal, target_id):
    if not isinstance(removal, NativeRetainedRemoval) or removal.view is not view:
        raise ValueError("Native aura removal callbacks differ from snapshot")
    selected = aura_removal_snapshot(view, target_id)
    # The shared removal preflights every selected runner and owned child.
    # eZF has no dispellability or source-spell eligibility gate.
    return removal.remove(selected)


class NativeAuraRemovalHandler:
    """Execute eZF with the actual shared runner lifecycle and owned Qf view."""

    native_runner_value_verified = True

    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, retention, rng
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.retention, self.rng = context, retention, rng
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        from .combat_stat_handler import StatExecutionContext

        if effect.get("effect_class") != 316 or self.fight.phase != "active":
            raise ValueError("Missing actual native eZF family/fight")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Missing actual native aura-removal execution authority")
        if invocation.target_id is None:
            raise ValueError("Native eZF requires its actual bfs PV recipient")
        from .combat_state_managers import state_manager

        if state_manager(self.fight, invocation.target_id) is None:
            raise ValueError("Unregistered native eZF PV recipient")
        return context

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eZF event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
                _execution_status=-1,
            )

    def prepare(self, effect, values, invocation):
        from dataclasses import replace
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_value_transfer import apply_context_value

        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, 316, rng=self.rng)
        self.prepared[uid] = runner
        try:
            self._phase(effect, invocation, runner, 1)
            # eZF.C is empty. Only inherited eZR.n context forcing writes aSg.
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
            raise ValueError("Missing prepared native eZF runner")
        try:
            context = self._context(effect, invocation)
            if not context.executable:
                return False
            self._phase(effect, invocation, runner, 2)
            view = self.retention.view()
            removal = self.retention.removal(view)
            # Preflight ownership and serialization before mutating any aura.
            selected = aura_removal_snapshot(view, invocation.target_id)
            removal.plan(selected)
            from .combat_retained_runtime import group_payload
            from .combat_stat_effects import owned_effect_application
            from .combat_effects import _integer, _varint
            from wakfu_server.wire import proto_fields

            owner, owner_id = self.retention.container(invocation)
            if not isinstance(context.timing_payload, bytes):
                raise ValueError("Missing actual native eZF TimeDatas")
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
                effect_class=316,
                target_id=invocation.target_id,
                uid=runner.uid,
                running_effect_payload=payload,
            )
            removal.remove(selected)
            self.packets.append((13497, packet))
            if context.retained:
                self.fight.owned_stat_effects[runner.uid] = dict(
                    uid=runner.uid,
                    effect_class=316,
                    family="eZF",
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


def remove_aura_removal_runner(handler, uid):
    """Inherited removal does not recreate the auras already removed by eZF."""
    from .combat_effect_removal import running_effect_removal

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != "eZF" or row.get("effect_class") != 316:
        raise ValueError("Missing owned native eZF runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=316,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
