"""Owned equipment roots for the native effect motor, without lifecycle guesses.

Native eHi.bY passes the equipped fnR as PL even for roots appended by
fnR.ggP from BASIC/SPECIAL scroll definitions. Thus the retained identity and
level belong to the parent gear, never to the attached scroll or inventory UID.
This planner does not register effects or change combat snapshots.
"""
from .combat_character_copy_equipment import native_copied_equipment_catalog
from .combat_copied_equipment_plan import copied_equipment_plan
from .combat_copied_equipment_execution import equipment_effect_definitions
from .combat_effect_dispatch import UnsupportedEffectExecution


def plan(
    character,
    *,
    attachment_authority=None,
    catalog=None,
    templates=None,
    ordinary_only=False
):
    """Return ordered owned source groups with complete native definitions.

    attachment_authority(gear, shard_state, reference, field_tag) must return an
    explicit bool after validating native pattern compatibility and enablement.
    Unknown authority rejects; it never silently activates a persisted scroll.
    Ordinary roots are limited to passive304; flat bonuses remain snapshot-owned.
    Callers still must execute the complete closure transactionally through the
    native dispatcher, whose unsupported families remain fail-closed.
    """
    from wakfu_server.equipment import validate_sheet
    from wakfu_server.equipment_stats import CATALOG
    from wakfu_server.builds import effective_sheet_level, valid_index
    from wakfu_server.inventory_shards import validate
    from wakfu_server.wire import proto_fields

    index = character.get("active_build_index", 0)
    if not valid_index(index):
        raise ValueError("Invalid active equipment sheet")
    sheet = character.get("builds", {}).get(index, {})
    # No ordinary equipped source requires no build-level or native metadata.
    # Attached-source preparation retains its original validation path.
    if ordinary_only and sheet.get("equipment", "") == "":
        return ()
    adjusted = dict(character, level=effective_sheet_level(character, index))
    selected = validate_sheet(adjusted, bytes.fromhex(sheet.get("equipment", "")))
    if not selected:
        return ()
    owned = {item["uid"]: item for item in character.get("inventory_items", [])}
    native = native_copied_equipment_catalog() if catalog is None else catalog
    summaries = CATALOG if templates is None else templates
    result = []

    def source(gear, source_reference, tag, roots, parent):
        if not roots:
            return
        closure = equipment_effect_definitions({"roots": roots})
        result.append(
            dict(
                uid=gear["uid"],
                reference=gear["reference"],
                source_reference=source_reference,
                attachment_field=tag,
                roots=tuple(root["reference"] for root in roots),
                effects=closure,
                native_retained_container=dict(parent["native_retained_container"]),
            )
        )
        if ordinary_only:
            from .combat_equipment_passive_completeness import (
                unplanned_passive_effect_ids,
            )

            result[-1]["unplanned_passive_effect_ids"] = unplanned_passive_effect_ids(
                source_reference, parent, result[-1]["roots"], templates=summaries
            )

    def passive_roots(reference, native_plan, *, ordinary):
        summary = summaries.get(reference)
        if summary is None:
            raise UnsupportedEffectExecution(
                "Missing native equipment filter authority"
            )
        identities = {effect["id"]: effect for effect in summary["effects"]}
        result = []
        for root in native_plan["roots"]:
            identity = identities.get(root["reference"])
            if (
                identity is None
                or type(identity.get("native_variant")) is not int
                or type(identity.get("native_active_effect")) is not bool
            ):
                raise UnsupportedEffectExecution("Missing native eHi passive identity")
            if identity["native_variant"] != 0 or identity["native_active_effect"]:
                continue
            if ordinary and root["effect_class"] != 304:
                continue
            result.append(root)
        return result

    for entry in selected:
        gear = owned[entry["uid"]]
        parent = copied_equipment_plan(gear["reference"], native)
        if parent["status"] != "explicit_self_effects":
            raise UnsupportedEffectExecution(
                "Missing owned native equipment definition"
            )
        source(
            gear,
            gear["reference"],
            None,
            passive_roots(gear["reference"], parent, ordinary=True),
            parent,
        )
        if ordinary_only:
            continue
        state = gear.get("shard_state")
        if state is None:
            continue
        state = bytes(state)
        validate(state)
        fields = dict(proto_fields(state))
        for tag in (24, 32):
            reference = fields.get(tag, 0)
            reference = reference & 0xFFFFFFFF
            if reference >= (1 << 31):
                reference -= 1 << 32
            if reference == 0:
                continue
            if reference < 0 or not callable(attachment_authority):
                raise UnsupportedEffectExecution(
                    "Missing native sublimation eligibility authority"
                )
            eligible = attachment_authority(gear, state, reference, tag)
            if type(eligible) is not bool:
                raise UnsupportedEffectExecution(
                    "Unknown native sublimation eligibility"
                )
            if not eligible:
                continue  # Native fnR.a returns no iterator for disabled/ineligible roots.
            attached = copied_equipment_plan(reference, native)
            if attached["status"] != "explicit_self_effects":
                raise UnsupportedEffectExecution(
                    "Missing native sublimation definition"
                )
            source(
                gear,
                reference,
                tag,
                passive_roots(reference, attached, ordinary=False),
                parent,
            )
    return tuple(result)
