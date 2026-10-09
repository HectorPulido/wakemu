#!/usr/bin/env python3
"""Actual class capture: fresh empty Symbiot, native mark, owned lethal attack.

No roster slots, HP, deaths, grants or resources are injected. The opponent is
an existing original capturable profile at its original minimum level. Monster
AI and monster spell execution are outside this offline class-owned scope.
"""
import argparse
from copy import deepcopy
import json
import hashlib
from pathlib import Path
import random
import struct

import audit_ready_start as ready
from audit_class_character_copy_lifecycle import advance, reach
from audit_class_normal_casts import root_failure
from wakfu_server.characters.captured_roster import (
    OwnedCapturedRoster,
    roster_from_character,
)
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells, validate_deck


class ActualCapture:
    def __init__(self, capture_spell, target_reference, target_level):
        self.capture_spell = capture_spell
        self.target_reference = target_reference
        self.target_level = target_level

    def __call__(self, runtime, character, monster, deck, packets, stats):
        original = snapshot(runtime.fight)
        branch = deepcopy(runtime)
        result = dict(
            scope="actual_owned_class_capture320",
            gameplay_verified=False,
            opponent=dict(reference=monster["ref"], level=monster["level"]),
            injected_slots=False,
            injected_death=False,
            attempts=[],
        )
        trace = []

        def los(origin, target, state):
            return authoritative_visible(
                state.map_id,
                origin,
                target,
                state,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in state.actors.values() if a.hp > 0
                },
            )

        def prepare(uid):
            return prepare_server_spell(
                struct.pack(
                    ">qqiih",
                    character["id"],
                    uid,
                    *branch.fight.actors[monster["id"]].position
                ),
                character,
                {monster["id"]: monster},
                branch.fight,
                character["account_id"],
                deck,
                action_id=branch.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=random.Random(37),
            )

        try:
            if (monster["ref"], monster["level"]) != (
                self.target_reference,
                self.target_level,
            ):
                raise ValueError(
                    "Capture target differs from the original scoped opponent"
                )
            roster = roster_from_character(character)
            if not isinstance(roster, OwnedCapturedRoster) or roster.free_slots != 10:
                raise ValueError(
                    "Capture requires actual freshly constructed empty Symbiot"
                )
            result["fresh_roster"] = roster.to_record()
            result["owner_turns"] = reach(branch, character["id"])
            grant = grant_record(branch.fight, character["id"], self.capture_spell)
            if grant is None:
                raise ValueError(
                    "Actual Ready did not own the native capture parent action"
                )
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
            )
            target = branch.fight.actors[monster["id"]]
            source = adapter.actor_authority(branch.fight, target)
            result["target_authority"] = dict(
                breed_id=source.breed_id,
                native_actor_type=source.native_actor_type,
                native_real_level=source.native_real_level,
                targeting=source.targeting,
                fight_property_counts=adapter.actor_authority.property_counts(
                    branch.fight, target
                ),
                world_property_counts=adapter.actor_authority.world_property_counts(
                    branch.fight, target
                ),
            )
            before = snapshot(branch.fight)
            with combat_diagnostic_scope(
                lambda **event: trace.append(event), limit=8192
            ):
                marked = prepare(grant["uid"])
            if snapshot(branch.fight) != before:
                raise AssertionError(
                    "Capture mark preparation changed its actual source"
                )
            mark_events = [
                e for e in marked.fight.events if e["sequence"] > branch.fight.sequence
            ]
            mark_packets = commit_spell_transaction(
                branch, marked, stats_serializer=stats
            )
            result["mark"] = dict(
                status="actual_parent_committed",
                uid=grant["uid"],
                reference=self.capture_spell,
                costs=marked.plan["costs"],
                packet_count=len(mark_packets),
                events=mark_events,
                completed_effects=[e for e in trace if e.get("status") == "completed"],
            )
            result["status"] = "native_mark_committed_capture_pending"
            active = [
                uid
                for uid in validate_deck(deck, character["breed"], character["level"])[
                    "active"
                ]
                if uid
            ]
            for turn in range(8):
                if (
                    branch.fight.phase != "active"
                    or branch.fight.actors[monster["id"]].hp <= 0
                ):
                    break
                reach(branch, character["id"])
                choices = [(character["id"] << 32) | ref for ref in active]
                choices.extend(
                    row["uid"]
                    for row in granted_spells(branch.fight, character["id"]).values()
                    if row["reference"] != self.capture_spell
                )
                committed = False
                for uid in dict.fromkeys(choices):
                    before = snapshot(branch.fight)
                    attack_trace = []
                    row = dict(turn=turn, uid=uid)
                    try:
                        with combat_diagnostic_scope(
                            lambda **e: attack_trace.append(e), limit=8192
                        ):
                            attack = prepare(uid)
                        source_target = branch.fight.actors[monster["id"]]
                        target_after = attack.fight.actors[monster["id"]]
                        damage_events = [
                            e
                            for e in attack.fight.events
                            if e["sequence"] > branch.fight.sequence
                            and e.get("kind") == "damage"
                            and e.get("source_id") == character["id"]
                            and e.get("target_id") == monster["id"]
                        ]
                        if not damage_events or target_after.hp >= source_target.hp:
                            row["status"] = "prepared_without_actual_owned_damage"
                            result["attempts"].append(row)
                            continue
                        if snapshot(branch.fight) != before:
                            raise AssertionError(
                                "Owned attack preparation changed its source"
                            )
                        actual_hp_before = source_target.hp
                        row["target_subscriptions_before"] = [
                            dict(
                                uid=key,
                                reference=value["invocation"]["reference"],
                                state_uid=value.get("state_uid"),
                                masks=value.get("native_subscription_masks"),
                            )
                            for key, value in getattr(
                                branch.fight, "native_owned_group_effects", {}
                            ).items()
                            if value["invocation"]["target_id"] == monster["id"]
                        ]
                        attack_packets = commit_spell_transaction(
                            branch, attack, stats_serializer=stats
                        )
                        row.update(
                            status="actual_owned_attack_committed",
                            reference=attack.plan["spell_id"],
                            costs=attack.plan["costs"],
                            damage_events=damage_events,
                            hp_before=actual_hp_before,
                            hp_after=target_after.hp,
                            native_death_deliveries=getattr(
                                branch.fight, "native_death_event_deliveries", {}
                            ),
                            packet_count=len(attack_packets),
                            completed_effects=[
                                e
                                for e in attack_trace
                                if e.get("status") == "completed"
                            ],
                        )
                        result["attempts"].append(row)
                        committed = True
                        break
                    except Exception as error:
                        row.update(
                            status="rejected",
                            failure=root_failure(error, attack_trace),
                            preparation_source_preserved=snapshot(branch.fight)
                            == before,
                        )
                        result["attempts"].append(row)
                record = getattr(branch.fight, "native_captured_rosters", {}).get(
                    str(character["id"])
                )
                captured = (
                    OwnedCapturedRoster.from_record(
                        record, expected_owner_id=character["id"]
                    )
                    if record is not None
                    else roster
                )
                if captured.free_slots < 10:
                    result["captured_roster"] = captured.to_record()
                    result["captured_profile_ids"] = [
                        e.profile_id for e in captured.slots if e is not None
                    ]
                    if result["captured_profile_ids"] != [self.target_reference]:
                        raise AssertionError(
                            "Actual capture changed an unexpected Symbiot profile"
                        )
                    if branch.fight.actors[monster["id"]].hp != 0:
                        raise AssertionError(
                            "Capture observed before actual target death"
                        )
                    result["status"] = "actual_native_capture_after_owned_lethal_action"
                    break
                if branch.fight.phase != "active" or not committed:
                    break
                advance(branch)
            result["final_target_hp"] = branch.fight.actors[monster["id"]].hp
            result["final_phase"] = branch.fight.phase
            if result["status"] == "native_mark_committed_capture_pending":
                result["status"] = "native_mark_committed_capture_not_observed"
            result["checkpoint_serializable"] = bool(
                json.dumps(snapshot(branch.fight), allow_nan=False)
            )
        except Exception as error:
            result["failure"] = root_failure(error, trace)
            if "status" not in result:
                result["status"] = "rejected_before_native_mark"
        result["source_preserved"] = snapshot(runtime.fight) == original
        if not result["source_preserved"]:
            raise AssertionError("Capture audit changed its actual Ready source")
        return result


class RestoredCaptureSummon:
    def __call__(self, runtime, character, monster, deck, packets, stats):
        from class_spell_eligible_targets import eligible_cast_targets

        branch = deepcopy(runtime)
        steps = reach(branch, character["id"])
        grant = grant_record(branch.fight, character["id"], 7348)
        if grant is None:
            raise ValueError("Restored roster Ready did not grant native summon parent")

        def los(origin, target, fight):
            return authoritative_visible(
                fight.map_id,
                origin,
                target,
                fight,
                blocking_footprints={
                    a.id: {a.position[:2]} for a in fight.actors.values() if a.hp > 0
                },
            )

        _, adapter = server_runtime(
            character,
            {monster["id"]: monster},
            deck,
            action_id=branch.action_id + 1,
            critical=False,
        )
        selection = eligible_cast_targets(
            branch.fight,
            character,
            deck,
            grant["uid"],
            adapter=adapter,
            line_of_sight=los,
            actor_id=character["id"],
            limit=128,
            maximum_eligible=1,
        )
        if not selection["eligible"]:
            raise ValueError(
                "Restored actual captured descriptor has no legal summon cell"
            )
        cell = tuple(selection["eligible"][0]["target"])
        before_ids = set(branch.fight.actors)
        transaction = prepare_server_spell(
            struct.pack(">qqiih", character["id"], grant["uid"], *cell),
            character,
            {monster["id"]: monster},
            branch.fight,
            character["account_id"],
            deck,
            action_id=branch.action_id + 1,
            line_of_sight=los,
            critical=False,
            rng=random.Random(37),
        )
        created = [
            actor
            for key, actor in transaction.fight.actors.items()
            if key not in before_ids
            and getattr(actor, "native_summoned_from_symbiot", False)
        ]
        if len(created) != 1:
            raise AssertionError(
                "Restored captured parent did not construct exactly one native324 actor"
            )
        actor = created[0]
        delivered = commit_spell_transaction(
            branch, transaction, stats_serializer=stats
        )
        record = branch.fight.native_captured_rosters[str(character["id"])]
        roster = OwnedCapturedRoster.from_record(
            record, expected_owner_id=character["id"]
        )
        selected = roster.selected_slot
        if roster.available[selected] or roster.slots[selected] is None:
            raise AssertionError(
                "Actual324 did not consume the restored selected descriptor"
            )
        if (
            actor.native_summon_source["ref"] != roster.slots[selected].profile_id
            or actor.native_summon_source.get("native_captured_owner_id")
            != character["id"]
            or actor.native_summon_source.get("native_captured_slot") != selected
        ):
            raise AssertionError(
                "Native324 source differs from the actual restored owned descriptor"
            )
        json.dumps(snapshot(branch.fight), allow_nan=False)
        result = dict(
            status="captured_checkpoint_component_restored_and_native324_committed",
            injected_slots=False,
            restored_record=character["captured_roster"],
            actor_id=actor.id,
            actual_cell=list(actor.position),
            requested_cell=list(cell),
            native_source=actor.native_summon_source,
            packet_count=len(delivered),
            owner_turns=steps,
            selected_slot=selected,
            roster_after=record,
            checkpoint_serializable=True,
        )
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_movement_runtime import apply_client
        from wakfu_server.combat_area_transaction import prepare_area_movement

        result["summon_turns"] = reach(branch, actor.id)
        result["owned_attack"] = dict(status="not_observed", attempts=[], movements=[])
        attack = result["owned_attack"]
        # Walk only through the owned movement FSM if the original action's
        # casting guards reject its actual enemy. Resources are never refilled.
        for movement_step in range(5):
            for action in actor_action_book(branch.fight.actors[actor.id])["actions"]:
                trace = []
                target = branch.fight.actors[monster["id"]]
                try:
                    with combat_diagnostic_scope(
                        lambda **e: trace.append(e), limit=2048
                    ):
                        spell = prepare_server_spell(
                            struct.pack(
                                ">qqiih", actor.id, action["uid"], *target.position
                            ),
                            character,
                            {monster["id"]: monster},
                            branch.fight,
                            character["account_id"],
                            deck,
                            action_id=branch.action_id + 1,
                            line_of_sight=los,
                            critical=None,
                            rng=random.Random(43),
                        )
                    dealt = [
                        e
                        for e in spell.fight.events
                        if e["sequence"] > branch.fight.sequence
                        and e.get("kind") == "damage"
                        and e.get("source_id") == actor.id
                        and e.get("target_id") == monster["id"]
                        and e.get("amount", 0) > 0
                    ]
                    if not dealt:
                        attack["attempts"].append(
                            dict(
                                reference=action["reference"], status="no_owned_damage"
                            )
                        )
                        continue
                    hp_before = target.hp
                    emitted = commit_spell_transaction(
                        branch, spell, stats_serializer=stats
                    )
                    attack.update(
                        status="actual_controlled_summon_attack_committed",
                        reference=action["reference"],
                        uid=action["uid"],
                        critical=spell.plan.get("critical"),
                        hp_before=hp_before,
                        hp_after=branch.fight.actors[monster["id"]].hp,
                        damage_events=dealt,
                        costs=spell.plan["costs"],
                        packet_count=len(emitted),
                        completed_effects=[
                            e for e in trace if e.get("status") == "completed"
                        ],
                    )
                    json.dumps(snapshot(branch.fight), allow_nan=False)
                    result[
                        "status"
                    ] = "actual_capture_checkpoint_restore_summon_and_owned_attack_committed"
                    return result
                except Exception as error:
                    attack["attempts"].append(
                        dict(
                            reference=action["reference"],
                            status="rejected",
                            failure=root_failure(error, trace),
                        )
                    )
            moving = branch.fight.actors[actor.id]
            target = branch.fight.actors[monster["id"]]
            edges = [
                tuple(end)
                for start, end in (branch.fight.edges or ())
                if tuple(start) == moving.position
            ]
            edges.sort(
                key=lambda cell: (
                    abs(cell[0] - target.position[0])
                    + abs(cell[1] - target.position[1]),
                    cell,
                )
            )
            moved = False
            for destination in edges:
                try:
                    body = struct.pack(">q", actor.id) + struct.pack(
                        ">iih", *destination
                    )
                    emitted, event = apply_client(
                        branch,
                        character["account_id"],
                        body,
                        lambda selected_actor: stats(selected_actor, branch.fight),
                        area_provider=lambda preview, **boundary: prepare_area_movement(
                            character,
                            {monster["id"]: monster},
                            preview,
                            deck,
                            rng=random.Random(43),
                            **boundary
                        ),
                    )
                    attack["movements"].append(
                        dict(event=event, packet_count=len(emitted))
                    )
                    moved = True
                    break
                except ValueError:
                    continue
            if not moved:
                break
        return result


def run(output, *, target_reference=4, target_level=8, captured_report=None):
    if captured_report is not None:
        source_bytes = captured_report.read_bytes()
        source = json.loads(source_bytes)
        if (
            source.get("source_stable") is not True
            or source.get("tool_stable") is not True
        ):
            raise ValueError("Restoration requires a stable actual capture report")
        actual = source["rows"][0]["runtime_access"]
        if actual.get("status") != "actual_native_capture_after_owned_lethal_action":
            raise ValueError("No actual successful capture checkpoint to restore")
        record = json.loads(json.dumps(actual["captured_roster"]))

        def restore(character, breed, level, passive):
            character["captured_roster"] = OwnedCapturedRoster.from_record(
                record, expected_owner_id=character["id"]
            ).to_record()

        report = ready.run(
            output,
            cases_override=[(2, 200, None)],
            character_fixture_provider=restore,
            active_deck_provider=lambda breed, level, passive: [
                s["id"] for s in available_spells(breed, level) if s["kind"] == "active"
            ][:12],
            on_runtime=RestoredCaptureSummon(),
        )
        report["actual_capture_checkpoint_source"] = dict(
            path=str(captured_report),
            sha256=hashlib.sha256(source_bytes).hexdigest(),
            injected_slots=False,
        )
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
        return report
    # Native bulk inventory uniquely identifies7348 through state7128 to320.
    report = ready.run(
        output,
        cases_override=[(2, 200, None)],
        monster_reference=target_reference,
        monster_level=target_level,
        active_deck_provider=lambda breed, level, passive: [
            s["id"] for s in available_spells(breed, level) if s["kind"] == "active"
        ][:12],
        on_runtime=ActualCapture(7348, target_reference, target_level),
    )
    actual = report["rows"][0].get("runtime_access", {})
    if actual.get("status") == "actual_native_capture_after_owned_lethal_action":
        # Restore the actual newly captured component from checkpoint JSON;
        # interrupted Fight FSMs are deliberately not resumed by the server.
        record = json.loads(json.dumps(actual["captured_roster"]))

        def restore(character, breed, level, passive):
            character["captured_roster"] = OwnedCapturedRoster.from_record(
                record, expected_owner_id=character["id"]
            ).to_record()

        subsequent = output.with_name(output.stem + "-restored-summon.json")
        report["restored_capture_summon"] = ready.run(
            subsequent,
            cases_override=[(2, 200, None)],
            character_fixture_provider=restore,
            active_deck_provider=lambda breed, level, passive: [
                s["id"] for s in available_spells(breed, level) if s["kind"] == "active"
            ][:12],
            on_runtime=RestoredCaptureSummon(),
        )
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--target-reference", type=int, default=4)
    parser.add_argument("--target-level", type=int, default=8)
    parser.add_argument("--captured-report", type=Path)
    args = parser.parse_args()
    run(
        args.output,
        target_reference=args.target_reference,
        target_level=args.target_level,
        captured_report=args.captured_report,
    )
