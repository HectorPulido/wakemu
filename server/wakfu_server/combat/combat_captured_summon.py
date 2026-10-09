"""eZr324 captured descriptor preparation and ordered shared creation callbacks.

Only an owned selected descriptor supplies a profile seed. Constructor/book and
native fan characteristic scaling must come from source-verified providers.
"""
from dataclasses import dataclass, replace
import struct
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    CapturedCreature,
)
from wakfu_server.combat_summon import SummonSpecification


def _float(value):
    return struct.unpack(">f", struct.pack(">f", value))[0]


@dataclass(frozen=True)
class CapturedSummonPlan:
    specification: SummonSpecification | None
    owner_id: int
    selected_slot: int
    actor_id: int
    name: str | None
    descriptor_entry: CapturedCreature | None
    main_factor: float
    secondary_factor: float
    allowed: bool


def captured_summon_plan(
    effect,
    values,
    roster,
    *,
    caster_id,
    caster_level,
    caster_direction,
    caster_team,
    allocate_uid
):
    if effect.get("effect_class") != 324 or not isinstance(roster, OwnedCapturedRoster):
        raise ValueError("Native324 requires actual owned Symbiot component")
    if roster.owner_id != caster_id or not callable(allocate_uid):
        raise ValueError("Missing native324 descriptor owner/UID authority")
    parameters = tuple(values["parameters"])
    if any(
        type(value) is not int or not -(1 << 31) <= value < (1 << 31)
        for value in parameters
    ):
        raise ValueError("Missing native324 signed evaluated parameters")
    # eZr.C only the exact two-parameter variant enables fan factors.
    factors = (
        tuple(_float(_float(value) / _float(100.0)) for value in parameters)
        if len(parameters) == 2
        else (1.0, 1.0)
    )
    actor_id = allocate_uid()  # Native baj occurs before selected availability.
    if type(actor_id) is not int or not 0 < actor_id < (1 << 63):
        raise ValueError("Missing native PW captured summon UID")
    selected = roster.selected_creature
    available = selected is not None and roster.available[roster.selected_slot]
    if not available:
        return CapturedSummonPlan(
            None, caster_id, roster.selected_slot, actor_id, None, None, *factors, False
        )
    if (
        type(caster_level) is not int
        or not 0 <= caster_level <= 32767
        or type(caster_direction) is not int
        or not 0 <= caster_direction < 8
        or caster_team not in (0, 1)
    ):
        raise ValueError("Missing native324 caster level/geometry authority")
    anchor = "caster"
    if len(parameters) > 2:
        anchor = (
            "current"
            if parameters[2] == 0
            else "start"
            if parameters[2] == 1
            else "caster"
        )
    spec = SummonSpecification(
        selected.profile_id,
        caster_level,
        False,
        caster_direction,
        caster_team,
        anchor,
        parameters[3] if len(parameters) > 3 else 1,
    )
    return CapturedSummonPlan(
        spec,
        caster_id,
        roster.selected_slot,
        actor_id,
        selected.name,
        selected,
        *factors,
        True
    )


class NativeCapturedSummonPipeline:
    """eZr.c order: shared factory, fan, lE(true), unavailable slot.

    Factory receives the source-verified captured descriptor, not a fabricated307
    descriptor. Runtime registration, payload and roster persistence are explicit
    callbacks: this module never defaults missing native authority.
    """

    def __init__(
        self,
        *,
        profile_descriptor,
        create,
        scale_characteristics,
        mark_symbiot,
        commit_roster
    ):
        self.profile_descriptor = profile_descriptor
        self.create = create
        self.scale_characteristics = scale_characteristics
        self.mark_symbiot = mark_symbiot
        self.commit_roster = commit_roster
        if not all(
            callable(callback)
            for callback in (
                profile_descriptor,
                create,
                scale_characteristics,
                mark_symbiot,
                commit_roster,
            )
        ):
            raise ValueError("Complete native324 construction providers required")

    def execute(self, plan, roster, *, preview, cell):
        if not isinstance(plan, CapturedSummonPlan) or not isinstance(
            roster, OwnedCapturedRoster
        ):
            raise ValueError("Prepared owned native324 plan required")
        if plan.owner_id != roster.owner_id:
            raise ValueError("Native324 prepared roster owner changed")
        if not plan.allowed:
            return None
        selected = (
            roster.slots[plan.selected_slot] if 0 <= plan.selected_slot < 10 else None
        )
        if selected is None:
            return None  # eZr.c rechecks actual selected slot before factory.
        descriptor = self.profile_descriptor(
            plan.descriptor_entry,
            owner_id=plan.owner_id,
            level=plan.specification.level,
            actor_id=plan.actor_id,
        )
        if descriptor is None:
            raise ValueError("Missing actual captured profile descriptor/book source")
        actor = self.create(
            preview,
            plan.specification,
            descriptor,
            caster_id=plan.owner_id,
            actor_id=plan.actor_id,
            cell=cell,
        )
        if actor is None:
            raise ValueError("Native captured summon factory returned no actor")
        self.scale_characteristics(actor, plan.main_factor, plan.secondary_factor)
        self.mark_symbiot(actor, True)  # eGj.lE(true) only after factory + fan.
        flags = list(roster.available)
        flags[plan.selected_slot] = False
        self.commit_roster(preview, replace(roster, available=tuple(flags)))
        return actor


def mark_captured_origin(preview, actor, plan):
    """Apply eGj.lE(true) to actual registered actor and current authority.

    The shared factory installs false first. Updating only a UI flag would leave
    eOU/dTC reading a stale registered descriptor; both snapshots must advance.
    """
    if (
        not isinstance(plan, CapturedSummonPlan)
        or not plan.allowed
        or preview.actors.get(actor.id) is not actor
        or actor.id != plan.actor_id
    ):
        raise ValueError("Actual registered native324 actor required")
    source = getattr(actor, "native_summon_source", None)
    records = getattr(preview, "native_summon_registrations", None)
    row = records.get(actor.id) if isinstance(records, dict) else None
    authority = row.get("authority") if isinstance(row, dict) else None
    if (
        not isinstance(source, dict)
        or not isinstance(authority, dict)
        or source.get("ref") != plan.specification.reference
        or source.get("level") != plan.specification.level
        or source.get("caster_id") != plan.owner_id
        or authority.get("breed_id") != plan.specification.reference
        or authority.get("native_real_level") != plan.specification.level
    ):
        raise ValueError("Captured source and current actor authority disagree")
    actor.native_summoned_from_symbiot = True
    actor.native_summon_source = {
        **source,
        "native_symbiot_source": "eZr324.after_common_factory_and_fan.lE_true",
        "native_captured_slot": plan.selected_slot,
        "native_captured_owner_id": plan.owner_id,
    }
    preview.native_summon_registrations = {
        **records,
        actor.id: {
            **row,
            "authority": {**authority, "native_summoned_from_symbiot": True},
        },
    }
