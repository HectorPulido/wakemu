"""Installed eVX327/eVY328/eXB342 actor hooks and their exact owned runners.

Installed eGj consumers are empty in every installed actor subtype. Running
identity, notifications, lifetime, serialization and removal remain observable.
No server AI command is inferred from the native order operand.
"""
from dataclasses import dataclass, replace

FAMILIES = {327: "eVX", 328: "eVY", 342: "eXB"}


@dataclass(frozen=True)
class NativeOrderCell:
    x: int
    y: int
    z: int

    def __post_init__(self):
        if (
            any(
                type(value) is not int or not -(1 << 31) <= value < (1 << 31)
                for value in (self.x, self.y)
            )
            or type(self.z) is not int
            or not -32768 <= self.z <= 32767
        ):
            raise ValueError("Missing actual native order cell")

    def payload(self):
        from .combat_effects import _integer

        return b"".join(
            _integer(key, value)
            for key, value in enumerate((self.x, self.y, self.z), 1)
        )


def order_additional(family, *, target_long=0, cell=None):
    from .combat_effects import _integer, _varint

    if family == 327:
        if type(target_long) is not int or not -(1 << 63) <= target_long < (1 << 63):
            raise ValueError("Missing native eVX serialized long")
        return _integer(13, target_long)
    if family == 328:
        if not isinstance(cell, NativeOrderCell):
            raise ValueError("Missing calculated eVY native cell")
        value = cell.payload()
        return _varint(15 << 3 | 2) + _varint(len(value)) + value
    if family == 342:
        return b""
    raise ValueError("Unknown native actor hook family")


class NativeOrderHookHandler:
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
        actor_authority
    ):
        self.fight, self.packets, self.retention = fight, packets, retention
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.rng, self.actor_authority = context, rng, actor_authority
        self.event_lifecycle = None
        self.prepared = {}

    def _context(self, effect, invocation):
        from .combat_stat_handler import StatExecutionContext
        from .combat_native_actor_lookup import native_actor
        from .combat_runtime_adapter import NativeActorAuthority

        family = effect.get("effect_class")
        if family not in FAMILIES or self.fight.phase != "active":
            raise ValueError("Missing native actor hook family/fight")
        count = 0 if family == 342 else 1
        if (
            effect.get("parameter_count") != count
            or len(effect["parameters"]) != count * 2
        ):
            raise ValueError("Unaudited native actor hook parameter schema")
        masks = effect.get("target_masks")
        if not isinstance(masks, (list, tuple)) or len(masks) != 7 or any(masks[:6]):
            raise ValueError("Unaudited native actor hook subscription")
        if not callable(self.actor_authority) or self.retention.fight is not self.fight:
            raise ValueError("Missing actual actor/container authority")
        # All supported registered fighters represent eGj. Areas and absent PVs
        # need their own delivery contract; do not silently treat them as actors.
        for identity in (invocation.caster_id, invocation.target_id):
            actor = native_actor(self.fight, identity)
            if actor is None or not isinstance(
                self.actor_authority(self.fight, actor), NativeActorAuthority
            ):
                raise ValueError("Missing actual registered eGj actor authority")
        self.retention.container(invocation)
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
            or type(ctx.executable) is not bool
            or type(ctx.retained) is not bool
            or not isinstance(ctx.timing_payload, bytes)
        ):
            raise ValueError("Missing native actor hook timing/execution authority")
        if self.event_lifecycle is None:
            raise ValueError("Missing native actor hook event lifecycle")
        return ctx

    def _phase(self, effect, invocation, runner, channel):
        self.event_lifecycle.phase(
            effect,
            invocation,
            uid=runner.uid,
            value=runner.value,
            channel=channel,
            runner_modifier=runner,
            _event_ids=tuple(
                sorted(
                    ({0} if effect["effect_class"] in (327, 328) else set())
                    | set(effect["target_masks"][6] or ())
                )
            ),
            _execution_status=-1,
        )

    def prepare(self, effect, values, invocation):
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_parameters import parameter_value
        from .combat_value_transfer import apply_context_value

        self._context(effect, invocation)
        if invocation.native_running_uid is not None:
            raise ValueError("Unaudited restored native actor hook runner")
        family = effect["effect_class"]
        runner = NativeRunnerAmount(self.allocate_uid(), family, rng=self.rng)
        invocation = replace(invocation, native_running_uid=runner.uid)
        try:
            self._phase(effect, invocation, runner, 1)
            amount = (
                0
                if family == 342
                else parameter_value(effect["parameters"], 0, invocation.level)
            )
            runner.set_calculated(
                apply_context_value(
                    amount,
                    None
                    if invocation.native_context_hex is None
                    else bytes.fromhex(invocation.native_context_hex),
                )
            )
            cell = NativeOrderCell(*invocation.cell) if family == 328 else None
            self.prepared[runner.uid] = (runner, cell, invocation)
            return invocation
        except BaseException:
            self.cancel_prepared(invocation)
            raise

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        from .combat_effects import _integer, _varint
        from .combat_retained_runtime import group_payload
        from .combat_stat_effects import owned_effect_application
        from .combat_runner_callbacks import notify_runner_value
        from wakfu_server.wire import proto_fields

        if invocation.native_running_uid is None:
            invocation = self.prepare(effect, values, invocation)
        pair = self.prepared.get(invocation.native_running_uid)
        if pair is None or pair[2] != invocation:
            raise ValueError("Missing exact prepared native actor hook identity")
        runner, cell, _ = pair
        try:
            ctx = self._context(effect, invocation)
            if not ctx.executable:
                return False
            self._phase(effect, invocation, runner, 2)
            ctx = self._context(effect, invocation)
            if not ctx.executable:
                return False
            family = effect["effect_class"]
            owner, identity = self.retention.container(invocation)
            clock = b"".join(
                _integer(tag >> 3, value)
                if tag & 7 == 0
                else _varint(tag) + _varint(len(value)) + value
                for tag, value in proto_fields(ctx.timing_payload)
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
                container_id=identity,
                timing_payload=clock,
                initial_value=runner.value,
                context_payload=None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
            additional = order_additional(family, cell=cell)
            if additional:
                payload += _varint(8 << 3 | 2) + _varint(len(additional)) + additional
            packet = owned_effect_application(
                self.fight.id,
                self.action_id,
                effect_class=family,
                target_id=invocation.target_id,
                uid=runner.uid,
                running_effect_payload=payload,
            )
            # eGj.d/e/frY have exact empty bodies across the installed hierarchy.
            # PR.b/d publishes this owned application; Qe.a still performs L3/L4
            # and the actual synchronous PR.f value callback below.
            self.packets.append((13497, packet))
            if ctx.retained:
                self.fight.owned_stat_effects[runner.uid] = dict(
                    uid=runner.uid,
                    effect_class=family,
                    family=FAMILIES[family],
                    caster_id=invocation.caster_id,
                    target_id=invocation.target_id,
                    actual=0,
                    stat_id=None,
                    payload=payload.hex(),
                    state_uid=invocation.state_uid,
                    timer=None if ctx.timer is None else dict(vars(ctx.timer)),
                )
                self.retention.register_applied_stat(effect, invocation, runner.uid)
            runner.finish_application()
            self._phase(effect, invocation, runner, 3)
            self._phase(effect, invocation, runner, 4)
            notify_runner_value(invocation, runner.value)
            return True
        finally:
            self.cancel_prepared(invocation)


def remove_order_hook(handler, uid):
    from .combat_effect_removal import running_effect_removal, _identity_fields

    row = handler.fight.owned_stat_effects[uid]
    if row.get("family") != FAMILIES.get(row.get("effect_class")):
        raise ValueError("Missing actual owned native order hook")
    payload = bytes.fromhex(row["payload"])
    fields = _identity_fields(payload)
    if fields.get(1) != uid:
        raise ValueError("Native order hook removal UID mismatch")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=row["effect_class"],
        target_id=row["target_id"],
        uid=uid,
        running_effect_payload=payload,
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
