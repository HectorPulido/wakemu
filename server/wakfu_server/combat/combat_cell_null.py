"""Native402/eXG: one cell application, inherited eXE execution status.

No actor characteristic changes. A retained instance belongs to the caster's
manager; the wire target is absent and must never be replaced with that owner.
Subscribed cell listeners require separate native clone registration support.
"""
from .combat_effects import _integer, _varint
from .combat_displacement import position_payload
from .combat_stat_effects import null_execution_status
from .combat_stat_handler import StatExecutionContext
from .combat_effect_removal import running_effect_removal
from .combat_observation_delivery import evaluated_application_from_observation


def cell_null_payload(
    *, uid, base_uid, reference, caster_id, cell, status, timing_payload=None
):
    if base_uid is None:
        base_uid = uid
    if (
        type(uid) is not int
        or not 0 < uid < 1 << 63
        or type(base_uid) is not int
        or not 0 <= base_uid < 1 << 63
        or type(reference) is not int
        or not 0 < reference < 1 << 31
        or type(caster_id) is not int
        or caster_id == 0
        or not -(1 << 63) <= caster_id < 1 << 63
        or type(status) is not int
        or not -128 <= status <= 127
    ):
        raise ValueError("Invalid native cell null identity/status")
    position = position_payload(cell)
    payload = b"".join(
        _integer(k, v) for k, v in ((1, uid), (2, base_uid), (3, reference), (4, 0))
    )
    payload += b"\x2a" + _varint(len(position)) + position + _integer(6, caster_id)
    if not isinstance(timing_payload, bytes):
        raise ValueError("Unknown native cell null TimeDatas")
    timing = (timing_payload or b"") + _integer(2, status) + _integer(5, 1)
    return payload + b"\x5a" + _varint(len(timing)) + timing


class NativeCellNullHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context = (
            action_id,
            allocate_uid,
            context,
        )

    def __call__(self, effect, values, invocation):
        if (
            effect["effect_class"] != 402
            or invocation.target_id is not None
            or self.fight.phase != "active"
            or invocation.caster_id not in self.fight.actors
        ):
            raise ValueError("Native eXG requires a caster-owned cell application")
        if any(effect["target_masks"][:6]) or invocation.native_running_uid is not None:
            raise ValueError("Native subscribed cell null clone registration unaudited")
        if set(effect["native_effect_flags"]) - {1, 17}:
            raise ValueError("Unaudited native cell null flags")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
            or type(context.executable) is not bool
            or type(context.retained) is not bool
        ):
            raise ValueError("Native cell null execution/timing authority required")
        if not context.executable:
            return False
        status = null_execution_status(effect["parameters"])
        uid = self.allocate_uid()
        payload = cell_null_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            reference=invocation.reference,
            caster_id=invocation.caster_id,
            cell=invocation.cell,
            status=status,
            timing_payload=context.timing_payload,
        )
        packet = running_effect_removal(
            self.fight.id,
            self.action_id,
            effect_class=402,
            target_id=invocation.caster_id,
            uid=uid,
            running_effect_payload=payload,
        )[:-16]
        if context.retained:
            self.fight.owned_stat_effects[uid] = dict(
                uid=uid,
                effect_class=402,
                family="eXG",
                caster_id=invocation.caster_id,
                target_id=invocation.caster_id,
                payload_target_id=None,
                cell=invocation.cell,
                stat_id=None,
                actual=0,
                payload=payload.hex(),
                state_uid=invocation.state_uid,
                timer=None if context.timer is None else dict(vars(context.timer)),
            )
        # Instant cell effects own graphical scripts too. Native aTR (13497)
        # only observes their payload; aVo (12613) selects eVn.cbx and executes
        # the already evaluated null runner without inventing an actor target.
        opcode = 13497
        if not context.retained:
            packet = evaluated_application_from_observation(packet, execute=True)
            opcode = 12613
        self.packets.append((opcode, packet))
        return True


def remove_cell_null(handler, uid):
    row = handler.fight.owned_stat_effects[uid]
    if row["family"] != "eXG" or row["payload_target_id"] is not None:
        raise ValueError("Native cell null removal owner mismatch")
    packet = running_effect_removal(
        handler.fight.id,
        handler.action_id,
        effect_class=402,
        target_id=row["caster_id"],
        uid=uid,
        running_effect_payload=bytes.fromhex(row["payload"]),
    )
    del handler.fight.owned_stat_effects[uid]
    handler.packets.append((13560, packet))
    return True
