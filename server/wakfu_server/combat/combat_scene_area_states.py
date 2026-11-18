"""Explicit source-pinned state publishers on actual owned neutral faW PVs."""
from copy import deepcopy


def declarations(value):
    from .combat_scene_controlled_states import declarations as validate

    return validate(dict(controlled_state_programs=value, full_room_scope=True))


def install(fight, dispatcher):
    """Publish once at the first active runtime; never invent fighter innates."""
    if fight.phase != "active":
        return
    from .combat_encounter_scene_states import native_state_source_digest
    from .combat_definitions import state_profile
    from .combat_effect_dispatch import EffectInvocation
    from .combat_state_handler import StateCarrierContext
    from .combat_native_timing_context import native_time_payload
    from .combat_environment_glyphs import verify_environment_glyph
    from .combat_state_managers import registered_area_pv

    for source in tuple(getattr(fight, "native_environment_glyph_constructors", ())):
        plans = declarations(source.get("state_programs", ()))
        if not plans:
            continue
        row = fight.native_effect_areas.get(source["uid"])
        if row is None:
            continue  # Actual retired geometry is never respawned.
        verify_environment_glyph(fight, row)
        if not source.get("neutral_faw_constructor"):
            raise ValueError("Area state publisher requires reviewed neutral HP faW")
        receipt = row.get("native_scene_state_receipt")
        if receipt is not None:
            if receipt != list(plans):
                raise ValueError("Published area state programs changed")
            continue
        pv = registered_area_pv(fight, row["uid"])
        if pv is None or not pv.native_running_effect_manager:
            raise ValueError("Area state publisher lacks its actual Qf")
        handler, retention = (
            dispatcher.native_state_handler,
            dispatcher.native_retention,
        )
        for plan in plans:
            if (
                native_state_source_digest(handler.catalog, plan["state_id"])
                != plan["source_sha256"]
            ):
                raise ValueError("Area state source changed")
            native = state_profile(handler.catalog, plan["state_id"], plan["level"])
            if native["duration"] != -1 or native["realtime_duration"] != 0:
                raise ValueError("Area state requires indefinite native carrier")
        for plan in plans:
            context = StateCarrierContext(
                -1,
                0,
                False,
                None,
                None,
                False,
                False,
                False,
                0,
                native_time_payload(realtime_remaining=0),
            )
            invocation = EffectInvocation(
                2226,
                plan["level"],
                pv.id,
                pv.id,
                pv.position,
                native_retained_container={"present": False},
            )
            if not retention.apply_state_reference(
                handler,
                invocation,
                plan["state_id"],
                plan["level"],
                carrier_context=context,
                protected=True if plan["protected"] else None,
            ):
                raise ValueError("Original area scene state application rejected")
        row["native_scene_state_receipt"] = deepcopy(list(plans))


MARKER_DAMAGE_SELECTION = "reviewed-owned-marker-cell-damage-v1"


def rebind_scene_recipient(dispatcher, effect, invocation, ancestors):
    """Opt-in spatial reconstruction for a pinned area program's marker leaves.

    This explicitly reviewed server policy routes a native point damage leaf
    from its selected owned marker to occupants of that exact marker cell.
    Original selectors, criteria, amounts, state events and area geometry remain
    authoritative; ordinary chosen-PV execution never enters this branch.
    """
    from dataclasses import replace
    from .combat_encounter_effect_recipient import rebind_original_boss_recipient

    invocation = rebind_original_boss_recipient(
        dispatcher, effect, invocation, ancestors
    )
    if (
        effect.get("effect_class") not in (1, 2, 3, 4, 5)
        or effect.get("area_class") != "anD"
        or effect.get("native_target_selector") != {"class": "fcE", "mask": 1}
        or invocation.native_explicit_target is not True
        or invocation.wakemu_fresh_child_selection is not True
        or invocation.native_trigger_context is None
    ):
        return invocation
    fight = dispatcher.native_state_handler.fight
    sources = getattr(fight, "native_environment_glyph_constructors", ())
    declaration = next((s for s in sources if s["uid"] == invocation.caster_id), None)
    if (
        declaration is None
        or declaration.get("marker_damage_selection") != MARKER_DAMAGE_SELECTION
    ):
        return invocation
    row = fight.native_effect_areas.get(invocation.caster_id)
    marker = fight.native_effect_areas.get(invocation.target_id)
    if (
        row is None
        or marker is None
        or marker.get("owner_id") != invocation.caster_id
        or row.get("native_scene_state_receipt") != declaration.get("state_programs")
    ):
        return invocation
    carrier = next(
        (
            entry
            for entry in row["state_ledger"].entries
            if entry.uid == invocation.state_uid
        ),
        None,
    )
    if (
        carrier is None
        or not any(root in ancestors for root in carrier.effect_ids)
        or not any(
            p["state_id"] == carrier.reference for p in declaration["state_programs"]
        )
    ):
        return invocation
    return replace(
        invocation,
        target_id=None,
        cell=tuple(marker["cell"]),
        native_explicit_target=False,
        native_preselected_target=False,
        native_target_cell_argument=False,
    )
