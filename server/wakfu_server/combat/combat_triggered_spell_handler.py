"""eYZ runner; nested gameplay is an explicit atomic Wakemu server policy."""
from dataclasses import replace

from .combat_triggered_spell import native_triggered_spell_request
from .combat_stat_handler import StatExecutionContext
from .combat_trigger_value_modifier import NativeRunnerAmount
from .combat_parameters import parameter_value


class NativeTriggeredSpellHandler:
    native_runner_value_verified = True

    def __init__(
        self,
        fight,
        packets,
        *,
        action_id,
        allocate_uid,
        context,
        authority,
        rng,
        executor
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.authority, self.rng, self.executor = (
            context,
            authority,
            rng,
            executor,
        )
        self.event_lifecycle = None
        self.runners, self.prepared = {}, {}

    def _context(self, effect, invocation):
        if effect.get("effect_class") != 426 or self.fight.phase != "active":
            raise ValueError("Wrong native triggered-spell runner/fight")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
        ):
            raise ValueError("Missing native triggered-spell execution authority")
        if ctx.retained and invocation.target_id is None:
            raise ValueError(
                "Retained cell-triggered spell lacks an actual target manager"
            )
        return ctx

    def _phase(self, effect, invocation, uid, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native triggered-spell event masks")
            runner = self.runners[uid]
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
                _nullable_target=True,
                _execution_status=-1,
            )

    def cancel_prepared(self, invocation):
        uid = invocation.native_running_uid
        self.runners.pop(uid, None)
        self.prepared.pop(uid, None)

    def prepare(self, effect, values, invocation):
        self._context(effect, invocation)
        uid = self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        try:
            self.runners[uid] = NativeRunnerAmount(uid, 426, rng=self.rng)
            self._phase(effect, invocation, uid, 1)
            # C sets only private rHe; the native spell reference is evaluated
            # at level one during c, and must not inherit the parent's level.
            self.prepared[uid] = len(effect["parameters"]) < 6 or (
                parameter_value(effect["parameters"], 2, invocation.level) == 1
            )
            return invocation
        except Exception:
            self.cancel_prepared(invocation)
            raise

    def __call__(self, effect, values, invocation):
        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        uid = invocation.native_running_uid
        if uid not in self.prepared:
            raise ValueError("Missing prepared native triggered-spell runner")
        try:
            ctx = self._context(effect, invocation)
            if not ctx.executable:
                return False
            self._phase(effect, invocation, uid, 2)
            actor = self.fight.actors.get(invocation.caster_id)
            if actor is None:
                raise ValueError("Missing actual native triggered-spell caster")
            native = self.authority(self.fight, actor)
            target = self.fight.actors.get(invocation.target_id)
            if target is None and invocation.target_id is not None:
                from .combat_state_managers import registered_area_pv

                target = registered_area_pv(self.fight, invocation.target_id)
                if target is None:
                    raise ValueError("Missing actual native triggered-spell PV target")
            cell = target.position if target is not None else invocation.cell
            request = native_triggered_spell_request(
                effect["parameters"],
                invocation.level,
                caster_id=actor.id,
                target_cell=cell,
                caster_is_native_fighter=native.targeting.get("is_eGj"),
            )
            if request is None:
                return False
            request = replace(request, native_rhe=self.prepared[uid])
            payload = triggered_spell_payload(
                invocation,
                uid=uid,
                value=self.runners[uid].value,
                timing_payload=ctx.timing_payload,
            )
            self.executor(request, effect, invocation)
            import struct

            if not 0 < len(payload) <= 32767:
                raise ValueError("Invalid native triggered-spell application length")
            self.packets.append(
                (
                    12613,
                    struct.pack(
                        ">iiiBih",
                        self.fight.id,
                        self.action_id,
                        -1,
                        0,
                        426,
                        len(payload),
                    )
                    + payload,
                )
            )
            if ctx.retained:
                self.fight.owned_stat_effects[uid] = dict(
                    uid=uid,
                    effect_class=426,
                    family="eYZ",
                    caster_id=invocation.caster_id,
                    target_id=invocation.target_id,
                    actual=0,
                    stat_id=None,
                    payload=payload.hex(),
                    state_uid=invocation.state_uid,
                    timer=None if ctx.timer is None else dict(vars(ctx.timer)),
                )
                if self.event_lifecycle is not None:
                    self.event_lifecycle.register_applied(effect, invocation, uid)
            self.runners[uid].finish_application()
            self._phase(effect, invocation, uid, 3)
            self._phase(effect, invocation, uid, 4)
            from .combat_runner_callbacks import notify_runner_value

            notify_runner_value(invocation, self.runners[uid].value)
            return True
        finally:
            self.cancel_prepared(invocation)


def triggered_spell_payload(invocation, *, uid, value, timing_payload):
    from .combat_effects import _integer, _varint
    from .combat_displacement import position_payload
    from .combat_running_container import running_container_payload
    from .combat_running_context import running_context_payload

    if invocation.native_context_hex is None:
        raise ValueError("Missing actual eYZ current execution-context authority")
    payload = b"".join(
        _integer(k, v)
        for k, v in (
            (1, uid),
            (2, uid if invocation.base_uid is None else invocation.base_uid),
            (3, invocation.reference),
            (4, value),
        )
    )
    position = position_payload(invocation.cell)
    payload += b"\x2a" + _varint(len(position)) + position
    payload += _integer(6, invocation.caster_id)
    if invocation.target_id is not None:
        payload += _integer(7, invocation.target_id)
    payload += running_container_payload()
    clocks = (
        (b"" if timing_payload is None else timing_payload)
        + _integer(2, -1)
        + _integer(5, 1)
    )
    payload += b"\x5a" + _varint(len(clocks)) + clocks
    payload += running_context_payload(
        context_payload=bytes.fromhex(invocation.native_context_hex)
    )
    return payload


def remove_triggered_spell(handler, uid):
    """Inherited eZR/Qe removal does not undo an already triggered spell."""
    from .combat_effect_removal import running_effect_removal

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != "eYZ" or row.get("effect_class") != 426:
        raise ValueError("Not a retained native triggered-spell runner")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=426,
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
