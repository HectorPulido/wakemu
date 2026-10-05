"""Native843/eXU -> eYc: select one Qq, check bcF and call Qs.b.

Selection of an explicit Qq is distinct from coordinate fallback; a mismatched
explicit area does not fall back to another area. Replacement eYQ requires its
native derived definition and remains an explicit unsupported branch here.
"""
from .combat_effect_area import native_effect_areas, remove_owned_hour_area
from .combat_effect_area_queries import _rows
from .combat_effect_area_geometry import contains_area_cell
from .combat_retained_runtime import group_payload
from .combat_stat_effects import owned_effect_application
from .combat_stat_handler import StatExecutionContext
from .combat_effects import _integer, _varint
from .wire import proto_fields


def select_removal_area(fight, reference, target_id, cell):
    rows = tuple(_rows(fight))
    explicit = next((row for row in rows if row["uid"] == target_id), None)
    if explicit is not None:
        return (
            explicit if reference == -1 or explicit["reference"] == reference else None
        )
    candidates = tuple(
        row
        for row in rows
        if (reference == -1 or row["reference"] == reference)
        and contains_area_cell(row, cell)
    )
    # eYc takes the first Qs.bdm() entry, a native Trove map iteration.
    # Python insertion order cannot attest that ordering for overlapping areas.
    if len(candidates) > 1:
        raise ValueError("Native overlapping area iteration order is unaudited")
    return candidates[0] if candidates else None


class NativeAreaRemovalHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context, container):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context, self.container = (
            action_id,
            allocate_uid,
            context,
            container,
        )
        self.events = None

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 843:
            raise ValueError("Native eXU definition required")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Native area removal timing/source authority required")
        if not context.executable:
            return False
        parameters = values["parameters"]
        if not parameters:
            return False  # eYc.C leaves default zero; no generic area0 exists.
        if len(parameters) > 1 and parameters[1] != -1:
            raise ValueError("Native eYc replacement definition is unaudited")
        if context.retained or invocation.native_running_uid is not None:
            raise ValueError("Retained native eXU ownership is unaudited")
        row = select_removal_area(
            self.fight, parameters[0], invocation.target_id, invocation.cell
        )
        if row is None:
            return False  # eYc.fRS suppresses application notification.
        definition = native_effect_areas()[str(row["reference"])]
        if definition["raw_bdi"] is not True:
            return False  # Qq.bcF <- Qr.bdi.
        if self.events is None:
            raise ValueError("Native Qs removal callback provider required")
        uid = self.allocate_uid()
        owner, owner_id = self.container(invocation)
        # eZR.QH carries the executed bit; keep its real clock/status fields.
        clock = b"".join(
            _integer(tag >> 3, value)
            if tag & 7 == 0
            else _varint(tag) + _varint(len(value)) + value
            for tag, value in proto_fields(context.timing_payload)
            if tag != 40
        )
        clock += _integer(5, 1)
        payload = group_payload(
            uid=uid,
            base_uid=invocation.base_uid,
            generic_effect=invocation.reference,
            caster_id=invocation.caster_id,
            target_id=row["uid"],
            cell=invocation.cell,
            container_type=owner["container_type"],
            container_id=owner_id,
            timing_payload=clock,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        self.packets.append(
            (
                13497,
                owned_effect_application(
                    self.fight.id,
                    self.action_id,
                    effect_class=843,
                    target_id=row["uid"],
                    uid=uid,
                    running_effect_payload=payload,
                ),
            )
        )
        remove_owned_hour_area(self.fight, row["uid"], callbacks=self.events)
        return True
