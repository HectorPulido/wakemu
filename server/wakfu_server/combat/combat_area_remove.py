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
from wakfu_server.wire import proto_fields


def movement_blocking_area(row):
    """eXV.y consumes actual Qq.bcP, independently of removability bcF."""
    contract = row.get("native_area_contract")
    if contract in ("faW", "fbd"):
        key = (
            "native_faw_constructor" if contract == "faW" else "native_wall_constructor"
        )
        constructor = row.get(key)
        value = (
            constructor.get("movement_blocking")
            if isinstance(constructor, dict)
            else None
        )
        if type(value) is not bool:
            raise ValueError("Missing native Qq.bcP constructor authority")
        return value
    if contract in ("faZ", "faY", "faN", "faX", "faU", "fbc", "faP"):
        # First six inherit Qq.bcP=false. Registered faP is independently
        # validated by _rows as the audited nonblocking border constructor.
        return False
    raise ValueError("Unknown native Qq.bcP contract")


def select_removal_area(fight, reference, target_id, cell, *, eligible=None):
    rows = tuple(_rows(fight))
    explicit = next((row for row in rows if row["uid"] == target_id), None)
    if explicit is not None:
        return (
            explicit
            if (reference == -1 or explicit["reference"] == reference)
            and (eligible is None or eligible(explicit))
            else None
        )
    candidates = tuple(
        row
        for row in rows
        if (reference == -1 or row["reference"] == reference)
        and (eligible is None or eligible(row))
        and contains_area_cell(row, cell)
    )
    if len(candidates) > 1:
        from .combat_global_pv_collections import global_area_order

        by_uid = {row["uid"]: row for row in candidates}
        return next(by_uid[uid] for uid in global_area_order(fight) if uid in by_uid)
    return candidates[0] if candidates else None


class NativeAreaRemovalHandler:
    def __init__(
        self, fight, packets, *, action_id, allocate_uid, context, container, rng
    ):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid, self.context, self.container = (
            action_id,
            allocate_uid,
            context,
            container,
        )
        self.events = None
        self.rng = rng
        self.event_lifecycle = None
        self.prepared = {}

    def _phase(self, effect, invocation, runner, channel):
        if self.event_lifecycle is not None:
            masks = effect.get("target_masks")
            if not isinstance(masks, (list, tuple)) or len(masks) != 7:
                raise ValueError("Missing native eYc event masks")
            self.event_lifecycle.phase(
                effect,
                invocation,
                uid=runner.uid,
                value=runner.value,
                channel=channel,
                _event_ids=tuple(sorted({0, *(masks[6] or ())})),
                runner_modifier=runner,
                _nullable_target=True,
            )

    def prepare(self, effect, values, invocation):
        from dataclasses import replace
        from .combat_trigger_value_modifier import NativeRunnerAmount
        from .combat_value_transfer import apply_context_value

        if effect["effect_class"] not in (843, 909, 911, 1021):
            raise ValueError("Missing native eYc family")
        uid = invocation.native_running_uid or self.allocate_uid()
        invocation = replace(invocation, native_running_uid=uid)
        runner = NativeRunnerAmount(uid, effect["effect_class"], rng=self.rng)
        self._phase(effect, invocation, runner, 1)
        # C writes private selection fields, not aSg. Context forcing still
        # applies to the source runner amount independently of area reference.
        runner.set_calculated(
            apply_context_value(
                0,
                None
                if invocation.native_context_hex is None
                else bytes.fromhex(invocation.native_context_hex),
            )
        )
        self.prepared[uid] = runner
        return invocation

    def cancel_prepared(self, invocation):
        self.prepared.pop(invocation.native_running_uid, None)

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] not in (843, 909, 911, 1021):
            raise ValueError("Native eXU definition required")
        context = self.context(effect, invocation)
        if (
            not isinstance(context, StatExecutionContext)
            or context.source_guards_verified is not True
        ):
            raise ValueError("Native area removal timing/source authority required")
        runner = self.prepared.pop(invocation.native_running_uid, None)
        if invocation.native_running_uid is not None and runner is None:
            raise ValueError("Missing prepared native eYc runner")
        if not context.executable:
            return False
        if runner is None:
            invocation = self.prepare(effect, values, invocation)
            runner = self.prepared.pop(invocation.native_running_uid)
        self._phase(effect, invocation, runner, 2)
        context = self.context(effect, invocation)
        if not context.executable:
            return False
        parameters = values["parameters"]
        if not parameters:
            return False  # eYc.C leaves default zero; no generic area0 exists.
        if len(parameters) > 1 and parameters[1] != -1:
            raise ValueError("Native eYc replacement definition is unaudited")
        if context.retained:
            raise ValueError("Retained native eXU ownership is unaudited")
        row = select_removal_area(
            self.fight,
            parameters[0],
            invocation.target_id,
            invocation.cell,
            eligible=movement_blocking_area if effect["effect_class"] == 1021 else None,
        )
        if row is None:
            return False  # eYc.fRS suppresses application notification.
        definition = native_effect_areas()[str(row["reference"])]
        if definition["raw_bdi"] is not True:
            return False  # Qq.bcF <- Qr.bdi.
        if self.events is None:
            raise ValueError("Native Qs removal callback provider required")
        uid = runner.uid
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
            initial_value=runner.value,
        )
        self.packets.append(
            (
                13497,
                owned_effect_application(
                    self.fight.id,
                    self.action_id,
                    effect_class=effect["effect_class"],
                    target_id=row["uid"],
                    uid=uid,
                    running_effect_payload=payload,
                ),
            )
        )
        remove_owned_hour_area(self.fight, row["uid"], callbacks=self.events)
        from dataclasses import replace

        delivered = replace(invocation, target_id=row["uid"])
        runner.finish_application()
        from .combat_state_managers import removed_area_pv_scope

        with removed_area_pv_scope(self.fight, row):
            for channel in (3, 4):
                self._phase(effect, delivered, runner, channel)
        return True
