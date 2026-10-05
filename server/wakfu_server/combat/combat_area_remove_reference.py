"""935/eXS: snapshot matching Qq.bct, then Qs.a(area,actual caster)."""
from .combat_effect_area import remove_owned_hour_area
from .combat_effect_area_queries import _rows
from .combat_stat_handler import StatExecutionContext
from .combat_retained_runtime import group_payload
from .combat_stat_effects import owned_effect_application
from .combat_effects import _integer, _varint
from .wire import proto_fields


class NativeAreaReferenceRemovalHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context, container):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.container = context, container
        self.events = None

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 935:
            raise ValueError("Native eXS definition required")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Native eXS execution authority required")
        if not context.executable:
            return False
        if context.retained or invocation.native_running_uid is not None:
            raise ValueError("Retained native eXS ownership is unaudited")
        parameters = values["parameters"]
        reference = parameters[0] if parameters else 0  # eXS.C defaults aSg to zero.
        if type(reference) is not int or not -(1 << 31) <= reference < (1 << 31):
            raise ValueError("Invalid native eXS signed reference")
        rows = tuple(row for row in _rows(self.fight) if row["reference"] == reference)
        if rows and self.events is None:
            raise ValueError("Native Qs removal callback authority required")
        if invocation.caster_id not in self.fight.actors:
            raise ValueError("Missing actual eXS caster")
        uid = self.allocate_uid()
        owner, owner_id = self.container(invocation)
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
            target_id=invocation.target_id,
            cell=invocation.cell,
            container_type=owner["container_type"],
            container_id=owner_id,
            timing_payload=clock,
            initial_value=reference,
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
                    effect_class=935,
                    target_id=invocation.caster_id
                    if invocation.target_id is None
                    else invocation.target_id,
                    uid=uid,
                    running_effect_payload=payload,
                ),
            )
        )
        for row in rows:
            remove_owned_hour_area(
                self.fight,
                row["uid"],
                callbacks=self.events,
                removal_target_id=invocation.caster_id,
            )
        return True
