"""Native eXm923 consumes live caster AP/MP through a fresh eWf30 payment."""
from dataclasses import replace
import struct
from .combat_parameters import parameter_value
from .combat_stat_handler import StatExecutionContext, _bounds, _current, _write
from .combat_stat_effects import apply_current_stat
from .combat_effects import _integer, _varint
from .combat_native_timing_context import native_time_payload


def prepared_payment(ap, mp, ap_limit, mp_limit):
    """eXm.C min/all, then i2b and eWf.a's GS.cu nonnegative byte clamp."""
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in (ap, mp, ap_limit, mp_limit)
    ):
        raise ValueError("Invalid native eXm live resources or limits")
    result = []
    for current, limit in ((ap, ap_limit), (mp, mp_limit)):
        requested = current if limit < 0 else min(current, limit)
        narrowed = ((requested + 128) % 256) - 128
        result.append(max(0, narrowed))
    return tuple(result)


class NativeConsumeResourcesHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )
        self.event_lifecycle = None
        self.event_lifecycle_factory = None

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 923 or len(effect["parameters"]) != 4:
            raise ValueError("Unsupported native eXm definition")
        from .combat_native_actor_lookup import native_actor

        caster = native_actor(self.fight, invocation.caster_id)
        if self.fight.phase != "active" or caster is None:
            raise ValueError("Missing native eXm caster")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Unverified native eXm execution guards")
        if not context.executable:
            return False
        if self.event_lifecycle is None and callable(self.event_lifecycle_factory):
            self.event_lifecycle = self.event_lifecycle_factory()
        if self.event_lifecycle is None:
            raise ValueError("Missing native eWf payment lifecycle authority")
        requested = prepared_payment(
            caster.ap,
            caster.mp,
            parameter_value(effect["parameters"], 0, invocation.level),
            parameter_value(effect["parameters"], 1, invocation.level),
        )
        for stat in (2, 3):
            _bounds(caster, stat)
        parent_uid = self.allocate_uid()
        # Fresh eWf.a is a constructor, not Qe.b clone: UID/base stay -1.
        uid = -1
        payment = replace(
            invocation,
            reference=-1,
            level=-1,
            caster_id=caster.id,
            target_id=caster.id,
            cell=(0, 0, 0),
            base_uid=None,
            state_uid=None,
            native_trigger_context=None,
            native_context_hex=None,
            native_running_uid=None,
            native_value_scope=None,
            native_retained_container={"present": False},
        )
        events = tuple(
            (
                0,
                *((55,) if requested[0] > 0 else ()),
                *((65,) if requested[1] > 0 else ()),
            )
        )
        synthetic = {
            "effect_class": 30,
            "native_effect_flags": [],
            "native_costs": {"ap": requested[0], "mp": requested[1], "wp": 0},
        }
        actual = []
        for stat, amount in zip((2, 3), requested):
            minimum, maximum = _bounds(caster, stat)
            current = _current(caster, stat)
            result = apply_current_stat(
                family="eWR",
                current=current,
                minimum=minimum,
                maximum=maximum,
                requested=amount,
                percent=False,
                executable=True,
                frozen=stat in caster.effect_frozen,
                source_guards_verified=True,
                limit_policy="NORMAL",
            )
            _write(self.fight, caster.id, caster, stat, result["current"])
            actual.append(((current - result["current"] + 128) % 256) - 128)
        # eWf.c rewrites its packed value after actual PA.oo consumption.
        packed = ((actual[0] | actual[1] << 8) + (1 << 31)) % (1 << 32) - (1 << 31)
        from .combat_effect_removal import _proto_replace

        timing = _proto_replace(native_time_payload(), 5, 0, _integer(5, 1))
        payload = b"".join(
            _integer(field, value)
            for field, value in ((1, uid), (2, -1), (3, -1), (4, packed))
        )
        position = b"".join(_integer(field, 0) for field in (1, 2, 3))
        payload += b"\x2a" + _varint(len(position)) + position
        payload += _integer(6, caster.id) + _integer(7, caster.id)
        payload += b"\x5a" + _varint(len(timing)) + timing
        if packed != 0:
            # cvY carries only the complete proto, unlike cvZ owned removal.
            self.packets.append(
                (
                    13497,
                    struct.pack(
                        ">iiiih", self.fight.id, self.action_id, -1, 30, len(payload)
                    )
                    + payload,
                )
            )
        synthetic["native_costs"] = {"ap": actual[0], "mp": actual[1], "wp": 0}
        for channel in (3, 4):
            self.event_lifecycle.phase(
                synthetic,
                payment,
                uid=uid,
                value=packed,
                channel=channel,
                _event_ids=events,
            )
        for channel in (3, 4):
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=parent_uid,
                value=0,
                channel=channel,
                _nullable_target=True,
                _event_ids=tuple(sorted({0, *(effect["target_masks"][6] or ())})),
            )
        return True
