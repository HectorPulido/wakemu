"""Owned native effect areas, kept separate from the actor roster (Qs/Qq)."""
from .combat_state_ledger import StateLedger
import json
from functools import lru_cache
from .paths import DATA_ROOT
from .combat_effect_area_codec import area_application
from .combat_stat_handler import StatExecutionContext
from .combat_area_removal_masks import area_removal_masks


@lru_cache(maxsize=1)
def native_effect_areas():
    return json.loads((DATA_ROOT / "native-effect-areas.json").read_text())["areas"]


def remove_owned_hour_area(fight, uid, *, callbacks=None, removal_target_id=None):
    """Qs.b removes only the specified owned record; no lifecycle producer.

    faZ.baE collateral cleanup belongs to the distinct Qq.b owner callback,
    and is deliberately not implied by removal from the area manager.
    """
    areas = getattr(fight, "native_effect_areas", {})
    row = areas.get(uid)
    if row is None:
        return ()
    if (
        row.get("native_hour_contract") is not True
        and row.get("native_area_contract") != "faY"
    ):
        raise ValueError("Unsupported native effect-area removal callbacks")
    if callbacks is None and any(row.get("child_effect_uids", {}).values()):
        raise ValueError("Owned area child cleanup provider required")
    retired = getattr(fight, "native_retired_area_managers", {})
    if uid in retired:
        raise ValueError("Duplicate retired native area manager")
    removed = areas.pop(uid)
    # Qs.a(Qq,PV) unregisters before delivering event10011.
    if callbacks is not None:
        if removal_target_id is None:
            callbacks.removed(removed)
        else:
            callbacks.removed(removed, target_id=removal_target_id)
    ledger = removed.get("state_ledger")
    has_children = any(
        (
            entry.get("container_kind") == "effect_area"
            and entry.get("container_id") == uid
        )
        or entry.get("manager_id") == uid
        for entry in getattr(fight, "native_retained_records", {}).values()
    )
    if (ledger is not None and ledger.entries) or has_children:
        # Qf and owned Qe/PL identities remain actual objects after Qs unregisters
        # the area. Keep their ledger out of spatial queries and the fighter roster.
        retired = getattr(fight, "native_retired_area_managers", None)
        if retired is None:
            retired = {}
            fight.native_retired_area_managers = retired
        retired[uid] = removed
    return (removed,)


class NativeEffectAreaHandler:
    def __init__(self, fight, packets, *, action_id, allocate_uid, context, container):
        self.fight, self.packets = fight, packets
        self.action_id, self.allocate_uid = action_id, allocate_uid
        self.context, self.container = context, container
        self.on_created = None

    def __call__(self, effect, values, invocation):
        if effect["effect_class"] != 315 or invocation.target_id is not None:
            raise ValueError("Native eYQ requires a cell application")
        ctx = self.context(effect, invocation)
        if (
            not isinstance(ctx, StatExecutionContext)
            or ctx.source_guards_verified is not True
        ):
            raise ValueError("Missing native effect-area execution authority")
        if not ctx.executable:
            return False
        if invocation.native_running_uid is not None:
            raise ValueError("Native retained area effect removal is unaudited")
        p = values["parameters"]
        if not p:
            raise ValueError("Missing native area reference")
        ref = p[0]
        definition = native_effect_areas().get(str(ref))
        if (
            definition is None
            or definition["type"] not in ("HOUR", "GLYPH")
            or type(definition.get("raw_bde")) is not int
            or (
                self.on_created is None
                and (
                    not definition.get("native_hour_contract")
                    or definition["effect_ids"]
                    or definition["entry_masks"]
                    or definition["exit_masks"]
                    or definition["native_shape_class"] != "anD"
                )
            )
        ):
            raise ValueError(
                "Native area callbacks or shape are unaudited: "
                f"reference={ref!r}, definition={definition!r}"
            )
        removal_masks = area_removal_masks(definition)
        if removal_masks and self.on_created is None:
            raise ValueError("Native area removal masks require callback authority")
        level = ((p[1] + 32768) % 65536) - 32768 if len(p) > 1 else invocation.level
        keep = len(p) > 2 and p[2] == 1
        direction = p[3] if len(p) > 3 and 0 <= p[3] <= 7 else None
        caster = self.fight.actors.get(invocation.caster_id)
        effective_direction = (
            direction if direction is not None else getattr(caster, "direction", 7)
        )
        if type(effective_direction) is not int or not 0 <= effective_direction <= 7:
            raise ValueError("Missing native area orientation")
        from .combat_effect_area_geometry import registered_area_cells

        cells = registered_area_cells(definition, invocation.cell, effective_direction)
        area_uid = self.allocate_uid()
        uid = self.allocate_uid()
        owner, owner_id = self.container(invocation)
        packet = area_application(
            self.fight.id,
            self.action_id,
            uid=uid,
            base_uid=invocation.base_uid,
            effect_reference=invocation.reference,
            area_reference=ref,
            area_uid=area_uid,
            level=level,
            keep_after=keep,
            direction=direction,
            caster_id=invocation.caster_id,
            cell=invocation.cell,
            timing_payload=ctx.timing_payload,
            container_type=owner["container_type"],
            container_id=owner_id,
            context_payload=None
            if invocation.native_context_hex is None
            else bytes.fromhex(invocation.native_context_hex),
        )
        areas = getattr(self.fight, "native_effect_areas", None)
        if areas is None:
            areas = {}
            self.fight.native_effect_areas = areas
        if area_uid in areas:
            raise ValueError("Duplicate native area UID")
        areas[area_uid] = dict(
            uid=area_uid,
            reference=ref,
            level=level,
            cell=tuple(invocation.cell),
            owner_id=invocation.caster_id,
            direction=effective_direction,
            keep_after=keep,
            native_hour_contract=definition["type"] == "HOUR",
            native_area_contract="faZ" if definition["type"] == "HOUR" else "faY",
            native_type_id=definition["native_type_id"],
            native_removal_masks=tuple(sorted(removal_masks)),
            native_cells_xy=cells,
            remaining_activations=definition["raw_bde"],
            native_running_effect_manager=12 in definition["native_area_properties"],
            child_effect_uids={},
            executing=False,
            effect_uid=uid,
            effect_reference=invocation.reference,
        )
        if areas[area_uid]["native_running_effect_manager"]:
            areas[area_uid]["state_ledger"] = StateLedger(area_uid)
        if ctx.retained:
            owned = getattr(self.fight, "native_owned_area_effects", None)
            if owned is None:
                owned = {}
                self.fight.native_owned_area_effects = owned
            owned[uid] = dict(
                uid=uid,
                area_uid=area_uid,
                effect_class=315,
                target_id=None,
                caster_id=invocation.caster_id,
                state_uid=invocation.state_uid,
                payload=packet[1][18:].hex(),
                keep_after=keep,
                executed=True,
            )
        self.packets.append(packet)
        if self.on_created is None and definition["effect_ids"]:
            raise ValueError("Native effect-area callback provider required")
        if self.on_created is not None:
            self.on_created(areas[area_uid])
        return True
