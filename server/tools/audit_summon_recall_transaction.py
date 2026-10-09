#!/usr/bin/env python3
"""Run source-tree eWA recall on an actually granted Osa captured summon.

Uses audit_owned_captured324_transaction's committed Ready/grant/creator
fixture and performs recall on a private branch before the baseline turns.
No live services, database, fake QI updates, or roster-slot cleanup are used.
"""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
from dataclasses import asdict, is_dataclass

from audit_owned_captured324_transaction import run as run_captured_transaction
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.characters.captured_roster import OwnedCapturedRoster


RECALL_REPORT_PATH = None


def _save_recall_report(report):
    """Keep callback evidence even when a postcondition rejects the preview."""
    if RECALL_REPORT_PATH is not None:
        RECALL_REPORT_PATH.write_text(
            json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
        )


def _summary(value):
    if is_dataclass(value):
        value = asdict(value)
    if isinstance(value, dict):
        return {str(key): _summary(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_summary(item) for item in value]
    if value is None or type(value) in (bool, int, float, str):
        return value
    return repr(value)


def _record_diagnostic(row, key, collect):
    """Record best-effort diagnostics without changing runtime behavior."""
    try:
        row[key] = collect()
    except Exception as error:
        errors = row.setdefault("diagnostic_errors", [])
        errors.append(f"{key}: {type(error).__name__}: {error}")


def _trace_native_resolution(
    resolver,
    effect,
    invocation,
    *,
    original_resolve,
    resolution_diagnostics,
    selector_diagnostics,
):
    """Trace the canonical resolver while preserving its result/exceptions."""
    import wakfu_server.combat_effect_resolver as resolver_module

    selector_module = resolver_module
    original_select = selector_module.select_native_effect_targets
    original_context = resolver.context
    candidate_globals = type(resolver).candidate_invocations.__globals__
    row = {
        "effect_reference": effect.get("reference"),
        "invocation_reference": invocation.reference,
        "effect_class": effect.get("effect_class"),
        "effect_variant": effect.get("variant"),
        "area": [effect.get("area_class"), effect.get("area_native")],
        "candidate_selector_patch_identity": (
            candidate_globals.get("select_native_effect_targets") is original_select
        ),
        "candidate_globals_module": candidate_globals.get("__name__"),
    }
    _record_diagnostic(
        row, "target_selector", lambda: _summary(effect.get("native_target_selector"))
    )
    _record_diagnostic(
        row, "target_masks", lambda: _summary(effect.get("target_masks"))
    )
    _record_diagnostic(
        row, "effect_flags", lambda: _summary(effect.get("native_effect_flags"))
    )
    _record_diagnostic(row, "invocation", lambda: _summary(invocation))
    direct_policies = resolver.direct_target_policies
    _record_diagnostic(
        row,
        "direct_target_policy",
        lambda: _summary(
            None
            if direct_policies is None
            else direct_policies.get(str(invocation.reference))
        ),
    )

    def traced_context(selected_effect, selected_invocation):
        context = original_context(selected_effect, selected_invocation)
        _record_diagnostic(row, "resolution_context", lambda: _summary(context))
        _record_diagnostic(
            row,
            "application_eligible",
            lambda: resolver_module.application_eligible(selected_effect, context),
        )

        def owner_flags():
            from wakfu_server.combat_delivery_owners import native_owner_flags

            return list(native_owner_flags(selected_effect))

        _record_diagnostic(row, "native_owner_flags", owner_flags)
        return context

    def traced_select(selected_effect, caster, center, actors, *, native_context=None):
        selector_row = {}
        _record_diagnostic(
            selector_row, "effect_reference", lambda: selected_effect.get("reference")
        )
        _record_diagnostic(
            selector_row, "invocation_reference", lambda: invocation.reference
        )
        _record_diagnostic(selector_row, "center", lambda: _summary(center))
        _record_diagnostic(
            selector_row,
            "caster",
            lambda: {
                "id": getattr(caster, "id", None),
                "position": _summary(getattr(caster, "position", None)),
            },
        )
        _record_diagnostic(
            selector_row,
            "candidate_actors",
            lambda: [
                {
                    "id": getattr(actor, "id", None),
                    "position": _summary(getattr(actor, "position", None)),
                    "hp": getattr(actor, "hp", None),
                    "team": getattr(actor, "team", None),
                    "physical_radius": getattr(actor, "physical_radius", None),
                }
                for actor in actors
            ],
        )
        _record_diagnostic(
            selector_row, "targeting_context", lambda: _summary(native_context)
        )
        try:
            selected = original_select(
                selected_effect,
                caster,
                center,
                actors,
                native_context=native_context,
            )
        except Exception as error:
            selector_row["selector_error"] = f"{type(error).__name__}: {error}"
            selector_diagnostics.append(selector_row)
            raise
        _record_diagnostic(
            selector_row,
            "selected_actor_ids",
            lambda: [actor.id for actor in selected],
        )
        selector_diagnostics.append(selector_row)
        return selected

    selector_module.select_native_effect_targets = traced_select
    resolver.context = traced_context
    try:
        result = original_resolve(resolver, effect, invocation)
    except Exception as error:
        row["resolution_error"] = f"{type(error).__name__}: {error}"
        resolution_diagnostics.append(row)
        raise
    finally:
        selector_module.select_native_effect_targets = original_select
        resolver.context = original_context
    _record_diagnostic(row, "selected_invocations", lambda: _summary(result))
    resolution_diagnostics.append(row)
    return result


def _actor_facts(fight, actor, authority):
    def selected(mapping_name, keys):
        mapping = getattr(actor, mapping_name, None)
        if not isinstance(mapping, dict):
            return None
        return {str(key): mapping.get(key) for key in keys}

    frozen = getattr(actor, "effect_frozen", None)
    if frozen is not None:
        try:
            frozen = sorted(frozen)
        except TypeError:
            frozen = _summary(frozen)
    properties = getattr(actor, "native_fight_properties", None)
    if properties is not None:
        try:
            properties = sorted(properties)
        except TypeError:
            properties = _summary(properties)
    registrations = getattr(fight, "native_summon_registrations", None)
    facts = {
        "actor_id": actor.id,
        "hp": actor.hp,
        "position": list(actor.position),
        "actor_type": getattr(actor, "native_actor_type", None),
        "is_player": getattr(actor, "is_player", None),
        "is_summon": getattr(actor, "is_summon", None),
        "controller_id": getattr(actor, "native_controller_id", None),
        "qi_obstacle_id": getattr(actor, "native_obstacle_id", None),
        "effect_stats": selected("effect_stats", (1, 14)),
        "effect_minima": selected("effect_minima", (1, 14)),
        "effect_maxima": selected("effect_maxima", (1, 14)),
        "effect_base_maxima": selected("effect_base_maxima", (1, 14)),
        "effect_frozen": frozen,
        "fight_properties": properties,
        "summon_source": _summary(getattr(actor, "native_summon_source", None)),
        "registration": _summary(
            registrations.get(actor.id) if isinstance(registrations, dict) else None
        ),
        "captured_source": _summary(getattr(actor, "native_captured_source", None)),
        "copy_source": _summary(getattr(actor, "native_copy_source", None)),
    }
    if callable(authority):
        try:
            facts["authority"] = _summary(authority(fight, actor))
        except Exception as error:
            facts["authority_error"] = f"{type(error).__name__}: {error}"
    return facts


def _recall_summon_authority(runtime, character, monster, deck):
    """Build the same owned authority from the actual server runtime factory."""
    from wakfu_server.combat_server_spell import server_runtime

    factory, _ = server_runtime(
        character,
        {monster["id"]: monster},
        deck,
        action_id=runtime.action_id + 1,
        critical=False,
        rng=random.Random(17),
    )
    authority = getattr(factory, "summon_authority", None)
    if not callable(authority):
        raise ValueError("Server runtime did not provide summon actor authority")
    return authority


def recall_committed_capture(
    runtime, character, monster, deck, stats, los, created_actor_id
):
    """Exercise spell 7348's actual HasStateFromUser(7134,target) recall arm."""
    report = {"status": "pending", "created_actor_id": created_actor_id}
    fight = runtime.fight
    owner_id = character["id"]
    owner = fight.actors[owner_id]
    target = fight.actors[created_actor_id]
    summon_authority = _recall_summon_authority(runtime, character, monster, deck)
    report["before"] = {
        "owner_id": owner_id,
        "target_id": target.id,
        "target_hp": target.hp,
        "target_position": list(target.position),
        "target_controller_id": getattr(target, "native_controller_id", None),
        "captured_roster": fight.native_captured_rosters[str(owner_id)],
        "qi_slot": target.native_obstacle_id,
        "target_qi_row": fight.native_qi_slots[target.native_obstacle_id],
        "global_fighter_status": fight.native_global_pv_collections["fighter_status"][
            str(created_actor_id)
        ],
        "owner_facts": _actor_facts(fight, owner, summon_authority),
        "target_facts": _actor_facts(fight, target, summon_authority),
        "retirement_record": _summary(
            getattr(fight, "native_summon_retirements", {}).get(created_actor_id)
        ),
    }
    source_state = snapshot(fight)
    roster_before = OwnedCapturedRoster.from_record(
        fight.native_captured_rosters[str(owner_id)], expected_owner_id=owner_id
    )
    grant = grant_record(fight, owner_id, 7348)
    if grant is None:
        report.update(status="rejected", reason="actual 7348 grant missing")
        return report
    report["grant"] = grant
    if (
        roster_before.selected_slot != 3
        or roster_before.available[3]
        or roster_before.slots[3] is None
        or roster_before.slots[3].profile_id != 5347
    ):
        report.update(status="rejected", reason="unexpected actual captured slot state")
        return report

    trace = []
    validation_diagnostics = []
    resolution_diagnostics = []
    selector_diagnostics = []
    from wakfu_server.combat_summon_recall import NativeSummonRecallHandler
    from wakfu_server.combat_effect_resolver import NativeEffectResolver

    original_validate = NativeSummonRecallHandler._validate
    original_resolve = NativeEffectResolver.__call__

    def traced_resolve(resolver, effect, invocation):
        if effect.get("effect_class") != 859:
            return original_resolve(resolver, effect, invocation)
        return _trace_native_resolution(
            resolver,
            effect,
            invocation,
            original_resolve=original_resolve,
            resolution_diagnostics=resolution_diagnostics,
            selector_diagnostics=selector_diagnostics,
        )

    def traced_validate(handler, effect, invocation):
        row = {
            "effect": {
                key: effect.get(key)
                for key in (
                    "reference",
                    "effect_class",
                    "criteria",
                    "parameters",
                    "native_execution_mode",
                    "native_definition_class",
                    "native_timing_definition",
                    "target_masks",
                    "native_effect_flags",
                )
            },
            "invocation": _summary(invocation),
            "fight_phase": handler.fight.phase,
            "caster": _actor_facts(
                handler.fight,
                handler.fight.actors[invocation.caster_id],
                summon_authority,
            )
            if invocation.caster_id in handler.fight.actors
            else None,
            "target": _actor_facts(
                handler.fight,
                handler.fight.actors[invocation.target_id],
                summon_authority,
            )
            if invocation.target_id in handler.fight.actors
            else None,
        }
        try:
            result = original_validate(handler, effect, invocation)
        except Exception as error:
            row["validation_error"] = f"{type(error).__name__}: {error}"
            validation_diagnostics.append(row)
            raise
        row["execution_context"] = _summary(result[-1])
        row["resolved_owner_id"] = result[0].id
        row["resolved_target_id"] = result[1].id
        validation_diagnostics.append(row)
        return result

    rng = random.Random(17)
    rng_before = rng.getstate()
    try:
        body = struct.pack(">qqiih", owner_id, grant["uid"], *target.position)
        NativeSummonRecallHandler._validate = traced_validate
        NativeEffectResolver.__call__ = traced_resolve
        try:
            with combat_diagnostic_scope(
                lambda **event: trace.append(event), limit=4096
            ):
                transaction = prepare_server_spell(
                    body,
                    character,
                    {monster["id"]: monster},
                    fight,
                    character["account_id"],
                    deck,
                    action_id=runtime.action_id + 1,
                    line_of_sight=los,
                    critical=False,
                    rng=rng,
                )
        finally:
            NativeSummonRecallHandler._validate = original_validate
            NativeEffectResolver.__call__ = original_resolve
    except Exception as error:
        if snapshot(fight) != source_state or rng.getstate() != rng_before:
            raise AssertionError(
                "Rejected recall changed the committed source branch"
            ) from error
        report.update(
            status="rejected",
            reason=str(error),
            exception=type(error).__name__,
            trace=trace[-24:],
            validation_diagnostics=validation_diagnostics,
            resolution_diagnostics=resolution_diagnostics,
            selector_diagnostics=selector_diagnostics,
            rollback=True,
        )
        return report

    preview = transaction.fight
    preview_target = preview.actors[created_actor_id]
    preview_before_validation = snapshot(preview)
    recall_events = [
        event
        for event in trace
        if event.get("event") == "combat_effect" and event.get("effect_class") == 859
    ]
    selected_trace = [
        event
        for event in trace
        if event.get("event") == "combat_effect"
        and (
            event.get("effect_class") == 859
            or "HasStateFromUser(7134" in event.get("criteria", "")
        )
    ]
    records = preview.native_pr_completion_authority["completed"]
    record = next(
        (
            item
            for item in records
            if item.get("effect_class") == 859
            and item.get("target_id") == created_actor_id
        ),
        None,
    )
    if not recall_events or record is None:
        report.update(
            status="not_executed",
            plan={
                key: transaction.plan.get(key)
                for key in (
                    "actor_id",
                    "spell_id",
                    "spell_uid",
                    "target_id",
                    "target",
                    "effect_ids",
                    "costs",
                )
            },
            target_state_entries=[
                {
                    "uid": entry.uid,
                    "reference": entry.reference,
                    "level": entry.level,
                    "caster_id": entry.caster_id,
                    "target_id": entry.target_id,
                }
                for entry in preview_target.state_ledger.entries
            ],
            completion_records=records,
            validation_diagnostics=validation_diagnostics,
            resolution_diagnostics=resolution_diagnostics,
            selector_diagnostics=selector_diagnostics,
            effect_events=recall_events,
            trace=selected_trace,
            diagnostic_trace=trace,
            preview_snapshot_sha256=hashlib.sha256(
                json.dumps(
                    preview_before_validation,
                    sort_keys=True,
                    separators=(",", ":"),
                    allow_nan=False,
                ).encode()
            ).hexdigest(),
            source_preserved=snapshot(fight) == source_state,
        )
        return report
    if not any(opcode == 12613 for opcode, _ in transaction.packets):
        raise AssertionError(
            "Executed family859 did not produce its native application"
        )
    if preview_target.hp != preview_target.effect_minima[1]:
        raise AssertionError(
            "Recall did not set the captured target to native HP minimum"
        )
    if (
        preview_target.effect_base_maxima[14] != 0
        or preview_target.effect_maxima[14] != 0
        or preview_target.effect_stats[14] != 0
    ):
        raise AssertionError("Recall did not apply KO_TIME raw maximum zero")
    if created_actor_id not in preview.actors:
        raise AssertionError(
            "Recall removed the captured fighter object without source proof"
        )
    slot_changes = [
        {
            "slot": index,
            "before": fight.native_qi_slots[index],
            "after": preview.native_qi_slots[index],
        }
        for index in range(len(fight.native_qi_slots))
        if fight.native_qi_slots[index] != preview.native_qi_slots[index]
    ]
    target_slot = target.native_obstacle_id
    retirement = getattr(preview, "native_summon_retirements", {}).get(created_actor_id)
    try:
        from wakfu_server.combat_summon_retirement import retired_summon_ids

        retired_ids = sorted(retired_summon_ids(preview))
        retirement_validation_error = None
    except Exception as error:
        retired_ids = None
        retirement_validation_error = f"{type(error).__name__}: {error}"
    from wakfu_server.combat_global_pv_collections import global_fighter_guards

    qi_retirement_verified = (
        created_actor_id in (retired_ids or ())
        and len(slot_changes) == 1
        and slot_changes[0]["slot"] == target_slot
        and slot_changes[0]["before"] == fight.native_qi_slots[target_slot]
        and slot_changes[0]["before"] is not None
        and slot_changes[0]["before"].get("identity") == ["actor", created_actor_id]
        and slot_changes[0]["after"] is None
        and isinstance(retirement, dict)
        and retirement.get("qi_slot") == target_slot
        and preview.actors[created_actor_id].native_obstacle_id == -1
        and global_fighter_guards(preview, created_actor_id)
        == {"baF": False, "baG": False, "baK": True}
    )
    report["post_state"] = {
        "qi_changed_slots": slot_changes,
        "qi_target_slot_before": target_slot,
        "qi_target_slot_after": preview.actors[created_actor_id].native_obstacle_id,
        "retirement_record": _summary(retirement),
        "retired_summon_ids": retired_ids,
        "retirement_validation_error": retirement_validation_error,
        "global_fighter_status": global_fighter_guards(preview, created_actor_id),
        "global_fighter_membership_before": _summary(
            fight.native_global_pv_collections["fighters"]
        ),
        "global_fighter_membership_after": _summary(
            preview.native_global_pv_collections["fighters"]
        ),
        "captured_roster_before": _summary(
            fight.native_captured_rosters[str(owner_id)]
        ),
        "captured_roster_after": _summary(
            preview.native_captured_rosters[str(owner_id)]
        ),
        "retirement_events": [
            _summary(event)
            for event in preview.events
            if event.get("kind") == "summon_out_of_play"
            and event.get("actor_id") == created_actor_id
        ],
        "qi_retirement_verified": qi_retirement_verified,
    }
    report.update(
        status="postcondition_failed"
        if slot_changes and not qi_retirement_verified
        else "executed",
        effect_events=recall_events,
        validation_diagnostics=validation_diagnostics,
        resolution_diagnostics=resolution_diagnostics,
        selector_diagnostics=selector_diagnostics,
        completion_notice=_summary(record),
        packet_count=len(transaction.packets),
        cast_plan={
            key: _summary(transaction.plan.get(key))
            for key in (
                "actor_id",
                "spell_id",
                "spell_uid",
                "target",
                "target_id",
                "costs",
                "native_casting_flags",
            )
            if key in transaction.plan
        },
        owner_resources_before={
            "ap": fight.actors[owner_id].ap,
            "mp": fight.actors[owner_id].mp,
            "wp": fight.actors[owner_id].effect_stats.get(4),
        },
        owner_resources_after={
            "ap": preview.actors[owner_id].ap,
            "mp": preview.actors[owner_id].mp,
            "wp": preview.actors[owner_id].effect_stats.get(4),
        },
        hp_after=preview_target.hp,
        ko_time_after=preview_target.effect_stats[14],
        source_preserved=snapshot(fight) == source_state,
        trace=selected_trace,
        diagnostic_trace=trace,
    )
    _save_recall_report(report)
    if slot_changes and not qi_retirement_verified:
        raise AssertionError(
            "Recall changed QI without a verified settled summon retirement"
        )
    if (
        preview.native_global_pv_collections["fighters"]
        != fight.native_global_pv_collections["fighters"]
    ):
        raise AssertionError("Recall modified fdt membership without source proof")
    roster_after = OwnedCapturedRoster.from_record(
        preview.native_captured_rosters[str(owner_id)], expected_owner_id=owner_id
    )
    roster_availability_changes = [
        index
        for index, (before, after) in enumerate(
            zip(roster_before.available, roster_after.available)
        )
        if before != after
    ]
    roster_source = getattr(target, "native_summon_source", None)
    captured_release_verified = False
    if qi_retirement_verified and retirement.get("captured") is True:
        release_slot = (
            roster_source.get("native_captured_slot")
            if isinstance(roster_source, dict)
            else None
        )
        captured_release_verified = (
            type(release_slot) is int
            and 0 <= release_slot < len(roster_before.available)
            and retirement.get("qi_slot") == target_slot
            and roster_before.selected_slot == roster_after.selected_slot
            and roster_before.slots == roster_after.slots
            and roster_availability_changes == [release_slot]
            and roster_before.available[release_slot] is False
            and roster_after.available[release_slot] is True
        )
    elif qi_retirement_verified:
        captured_release_verified = (
            roster_before.selected_slot == roster_after.selected_slot
            and roster_before.available == roster_after.available
            and roster_before.slots == roster_after.slots
        )
    else:
        captured_release_verified = (
            roster_before.selected_slot == roster_after.selected_slot
            and roster_before.available == roster_after.available
            and roster_before.slots == roster_after.slots
        )
    report["post_state"][
        "captured_availability_changed_slots"
    ] = roster_availability_changes
    report["post_state"]["captured_release_verified"] = captured_release_verified
    _save_recall_report(report)
    if not captured_release_verified:
        raise AssertionError("Recall changed captured slots without source proof")
    if len(records) != len(fight.native_pr_completion_authority["completed"]) + 1:
        raise AssertionError("Unexpected PR completion notice count")

    report.update(
        status="prepared",
        effect_events=recall_events,
        validation_diagnostics=validation_diagnostics,
        resolution_diagnostics=resolution_diagnostics,
        selector_diagnostics=selector_diagnostics,
        completion_notice=record,
        packet_count=len(transaction.packets),
        hp_after=preview_target.hp,
        ko_time_after=preview_target.effect_stats[14],
        roster_preserved=not roster_availability_changes,
        captured_slot_released=(
            bool(roster_availability_changes) and captured_release_verified
        ),
        global_fighter_membership_preserved=True,
        qi_slots_preserved=not slot_changes,
        qi_retirement_verified=qi_retirement_verified,
        source_preserved=snapshot(fight) == source_state,
        trace=selected_trace,
        diagnostic_trace=trace,
    )
    _save_recall_report(report)
    delivery = commit_spell_transaction(runtime, transaction, stats_serializer=stats)
    report["commit"] = {
        "packet_count": len(delivery),
        "action_id": runtime.action_id,
        "runtime_now_uses_transaction_fight": runtime.fight is transaction.fight,
    }
    report["status"] = "committed"
    report["post_commit"] = {
        "actor_present": created_actor_id in runtime.fight.actors,
        "target_hp": runtime.fight.actors[created_actor_id].hp,
        "selected_slot": OwnedCapturedRoster.from_record(
            runtime.fight.native_captured_rosters[str(owner_id)],
            expected_owner_id=owner_id,
        ).selected_slot,
        "slot_available": OwnedCapturedRoster.from_record(
            runtime.fight.native_captured_rosters[str(owner_id)],
            expected_owner_id=owner_id,
        ).available[3],
    }
    snapshot(runtime.fight)  # Ensure the completion authority stays checkpointable.
    _save_recall_report(report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    global RECALL_REPORT_PATH
    RECALL_REPORT_PATH = args.output.with_suffix(".recall.json")
    tool_sha_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report = run_captured_transaction(
        args.output,
        commit_lifecycle=True,
        captured_commit_callback=recall_committed_capture,
    )
    tool_sha_after = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    report["recall_callback_tool_sha256"] = tool_sha_after
    report["recall_callback_tool_source_stable"] = tool_sha_before == tool_sha_after
    report["source_stable"] = (
        report.get("source_stable") is True
        and report["recall_callback_tool_source_stable"]
    )
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    result = report.get("owned_captured_transaction", {}).get(
        "captured_commit_callback", {}
    )
    args.output.with_suffix(".recall.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    print(
        json.dumps(
            {
                "status": result.get("status"),
                "effect_events": result.get("effect_events"),
                "qi_slots_preserved": result.get("qi_slots_preserved"),
                "roster_preserved": result.get("roster_preserved"),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
