#!/usr/bin/env python3
"""Actual Ready -> owned7348 parent tree -> captured324, without live services/DB."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import struct
from unittest.mock import patch
import audit_ready_start as ready_audit
from wakfu_server.characters.captured_roster import (
    CapturedCreature,
    OwnedCapturedRoster,
)
from wakfu_server.combat_captured_profiles import native_captured_profiles
from wakfu_server.combat_server_spell import prepare_server_spell
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot


def exercise_lifecycle(
    transaction, created, character, monster, deck, los, details, context
):
    """Use the actual Ready message owner, commit boundary and turn callbacks."""
    from wakfu_server.combat_spell_commit import commit_spell_transaction

    runtime, stats = context["runtime"], context["stats"]
    delivery = commit_spell_transaction(runtime, transaction, stats_serializer=stats)
    assert runtime.fight is transaction.fight
    assert runtime.action_id == transaction.action_id
    json.dumps(snapshot(runtime.fight), allow_nan=False)
    lifecycle = dict(
        commit_completed=True,
        commit_packet_count=len(delivery),
        native_actions=list(delivery.native_actions),
        turns=[],
        abilities=[],
    )
    details["lifecycle"] = lifecycle
    if context.get("captured_commit_callback") is not None:
        details["captured_commit_callback"] = context["captured_commit_callback"](
            deepcopy(runtime), character, monster, deck, stats, los, created.id
        )
        # Restore the Ready serializer binding after the independent branch.
        stats(runtime.fight.current, runtime.fight)
    try:
        # Re-casting with the same owned slot must reject through real eON.
        before = snapshot(runtime.fight)
        rng = random.Random(9)
        rng_before = rng.getstate()
        grant = grant_record(runtime.fight, character["id"], 7348)
        occupied = {actor.position for actor in runtime.fight.actors.values()}
        origin = runtime.fight.actors[character["id"]].position
        empty = next(
            cell
            for cell in sorted(runtime.fight.walkable)
            if cell not in occupied
            and 1 <= abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 4
        )
        try:
            prepare_server_spell(
                struct.pack(">qqiih", character["id"], grant["uid"], *empty),
                character,
                {monster["id"]: monster},
                runtime.fight,
                character["account_id"],
                deck,
                action_id=runtime.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=rng,
            )
        except Exception as error:
            assert snapshot(runtime.fight) == before and rng.getstate() == rng_before
            lifecycle["post_commit_recast_rejection"] = str(error)
            lifecycle["post_commit_recast_diagnostic"] = getattr(
                error, "native_casting_diagnostic", None
            )
            lifecycle["rejected_cast_rollback"] = True
        else:
            raise AssertionError(
                "Unavailable captured slot accepted another parent cast"
            )
        for _ in range(len(runtime.fight.actors) * 2):
            current = runtime.fight.current
            if current.id == created.id:
                break
            packets = (
                runtime.end_turn(current.owner_id, current.id, current.turn_count)
                if current.controlled
                else runtime.end_server_turn(current.id, runtime.fight.turn_id)
            )
            ack = runtime.awaiting_ack
            if ack is not None:
                packets += runtime.acknowledge_turn(struct.pack(">i", ack))
            lifecycle["turns"].append(
                dict(actor_id=current.id, packet_count=len(packets), ack=ack)
            )
            json.dumps(snapshot(runtime.fight), allow_nan=False)
            roster = OwnedCapturedRoster.from_record(
                runtime.fight.native_captured_rosters[str(character["id"])],
                expected_owner_id=character["id"],
            )
            assert (
                roster.selected_slot == 3
                and not roster.available[3]
                and roster.slots[3].profile_id == 5347
            )
        lifecycle["slot_preserved_through_turns"] = True
        assert (
            runtime.fight.current.id == created.id
        ), "Created summon did not receive its native timeline turn"
        lifecycle["summon_turn_started"] = True
        actor = runtime.fight.actors[created.id]
        lifecycle["controlled"] = actor.controlled
        from class_spell_eligible_targets import eligible_cast_targets
        from wakfu_server.combat_server_spell import server_runtime

        _, adapter = server_runtime(
            character,
            {monster["id"]: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=random.Random(11),
        )
        ability_baseline = runtime
        lifecycle[
            "ability_branch_policy"
        ] = "Independent branches from the actual committed summon turn; no resource refill or actor override"
        for action in actor.native_summon_action_book["actions"]:
            runtime = deepcopy(ability_baseline)
            search = eligible_cast_targets(
                runtime.fight,
                character,
                deck,
                action["uid"],
                adapter=adapter,
                line_of_sight=los,
                actor_id=actor.id,
                limit=256,
                maximum_eligible=1,
            )
            if not search["eligible"]:
                lifecycle["abilities"].append(
                    dict(
                        reference=action["reference"],
                        status="eligibility_pending",
                        search=search,
                    )
                )
                continue
            legal_target = search["eligible"][0]["target"]
            before = snapshot(runtime.fight)
            rng = random.Random(11)
            rng_before = rng.getstate()
            trace = []
            hp_before = {
                identity: value.hp for identity, value in runtime.fight.actors.items()
            }
            try:
                with combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=8192
                ):
                    ability = prepare_server_spell(
                        struct.pack(">qqiih", actor.id, action["uid"], *legal_target),
                        character,
                        {monster["id"]: monster},
                        runtime.fight,
                        character["account_id"],
                        deck,
                        action_id=runtime.action_id + 1,
                        line_of_sight=los,
                        critical=False,
                        rng=rng,
                    )
                resource_before = dict(
                    ap=runtime.fight.actors[actor.id].ap,
                    mp=runtime.fight.actors[actor.id].mp,
                    wp=runtime.fight.actors[actor.id].effect_stats[4],
                )
                assert (
                    ability.fight.actors[actor.id].ap
                    == resource_before["ap"] - ability.plan["costs"]["ap"]
                )
                assert (
                    ability.fight.actors[actor.id].mp
                    == resource_before["mp"] - ability.plan["costs"]["mp"]
                )
                assert (
                    ability.fight.actors[actor.id].effect_stats[4]
                    == resource_before["wp"] - ability.plan["costs"]["wp"]
                )
                packets = commit_spell_transaction(
                    runtime, ability, stats_serializer=stats
                )
                json.dumps(snapshot(runtime.fight), allow_nan=False)
                lifecycle["abilities"].append(
                    dict(
                        reference=action["reference"],
                        status="committed",
                        target=list(legal_target),
                        costs=ability.plan["costs"],
                        resources_before=resource_before,
                        resources_after=dict(
                            ap=runtime.fight.actors[actor.id].ap,
                            mp=runtime.fight.actors[actor.id].mp,
                            wp=runtime.fight.actors[actor.id].effect_stats[4],
                        ),
                        target_actor_id=ability.plan.get("target_id"),
                        hp_before=hp_before,
                        hp_after={
                            identity: value.hp
                            for identity, value in runtime.fight.actors.items()
                        },
                        trace=trace,
                        packets=len(packets),
                        search=search,
                    )
                )
            except Exception as error:
                assert (
                    snapshot(runtime.fight) == before and rng.getstate() == rng_before
                )
                lifecycle["abilities"].append(
                    dict(
                        reference=action["reference"],
                        status="rejected",
                        target=list(legal_target),
                        reason=str(error),
                        rollback=True,
                        trace=trace,
                        search=search,
                    )
                )
        lifecycle["ability_committed"] = any(
            row["status"] == "committed" for row in lifecycle["abilities"]
        )
        lifecycle["status"] = (
            "all_book_abilities_committed_in_separate_branches"
            if all(row["status"] == "committed" for row in lifecycle["abilities"])
            else "partial_book_ability_evidence"
        )
    except Exception as error:
        lifecycle.update(
            status="lifecycle_pending",
            reason=str(error),
            exception=type(error).__name__,
        )


def run(output, *, commit_lifecycle=False, captured_commit_callback=None):
    tool_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    original_fixture = ready_audit.fixture_module.fixture
    details = {}
    runtime_context = {}

    def owned_fixture(*args, **kwargs):
        character, monster, fight = original_fixture(*args, **kwargs)
        profile = native_captured_profiles()["5347"]
        slots = [None] * 10
        slots[3] = CapturedCreature(3, 5347, profile["native_profile_name"])
        available = [False] * 10
        available[3] = True
        character["captured_roster"] = OwnedCapturedRoster(
            character["id"], tuple(slots), tuple(available), 3
        ).to_record()
        details["owned_fixture"] = character["captured_roster"]
        return character, monster, fight

    def on_ready(source, character, monster, deck, ready_packets):
        before = snapshot(source)
        if source.current.id != character["id"]:
            raise ValueError("Actual Ready does not currently select owned caster")
        grant = grant_record(source, character["id"], 7348)
        if grant is None:
            raise ValueError("Actual Ready has not installed native7348 grant")
        caster = source.actors[character["id"]]
        origin = caster.position
        occupied = {actor.position for actor in source.actors.values()}
        cells = sorted(
            (
                cell
                for cell in source.walkable
                if cell not in occupied
                and 1 <= abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]) <= 4
            ),
            key=lambda cell: (
                abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]),
                cell,
            ),
        )
        failures = []

        def los(a, b, preview):
            return authoritative_visible(
                source.map_id,
                a,
                b,
                preview,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in preview.actors.values()
                    if actor.hp > 0
                },
            )

        for cell in cells:
            rng = random.Random(7)
            rng_before = rng.getstate()
            trace = []
            try:
                with combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=8192
                ):
                    result = prepare_server_spell(
                        struct.pack(">qqiih", caster.id, grant["uid"], *cell),
                        character,
                        {monster["id"]: monster},
                        source,
                        character["account_id"],
                        deck,
                        action_id=runtime_context["runtime"].action_id + 1
                        if runtime_context
                        else 2,
                        line_of_sight=los,
                        critical=False,
                        rng=rng,
                    )
            except Exception as error:
                assert snapshot(source) == before, "Failed cast changed source fight"
                assert rng.getstate() == rng_before, "Failed cast changed source RNG"
                failures.append(
                    {
                        "cell": list(cell),
                        "reason": str(error),
                        "exception": type(error).__name__,
                        "trace_tail": trace[-16:],
                        "casting_diagnostic": getattr(
                            error, "native_casting_diagnostic", None
                        ),
                    }
                )
                continue
            assert snapshot(source) == before, "Prepared cast changed source fight"
            created = [
                actor
                for key, actor in result.fight.actors.items()
                if key not in source.actors
            ]
            if len(created) != 1:
                raise AssertionError(
                    f"Native7348 tree created{len(created)} actors, expected1"
                )
            actor = created[0]
            roster = OwnedCapturedRoster.from_record(
                result.fight.native_captured_rosters[str(caster.id)],
                expected_owner_id=caster.id,
            )
            assert roster.selected_slot == 3 and not roster.available[3]
            assert roster.slots[3].profile_id == 5347 and roster.free_slots == 9
            assert actor.native_summoned_from_symbiot is True
            assert actor.native_summon_source["ref"] == 5347
            assert actor.native_summon_source["level"] == caster.effective_level
            assert [
                row["reference"] for row in actor.native_summon_action_book["actions"]
            ] == [7356, 7357, 7358]
            assert (
                result.fight.actors[caster.id].ap
                == caster.ap - result.plan["costs"]["ap"]
            )
            assert (
                result.fight.actors[caster.id].mp
                == caster.mp - result.plan["costs"]["mp"]
            )
            json.dumps(snapshot(result.fight), allow_nan=False)
            delivery = result.fight.native_summon_creation_deliveries[actor.id]
            assert any(
                opcode == delivery["opcode"]
                and payload.hex() == delivery["payload_hex"]
                for opcode, payload in result.packets
            )
            details.update(
                status="transaction_completed",
                grant=grant,
                cell=list(cell),
                plan=result.plan,
                created_actor_id=actor.id,
                actual_book=actor.native_summon_action_book,
                costs=result.plan["costs"],
                slot_unavailable=True,
                selected_slot_preserved=True,
                plain_checkpoint=True,
                source_preserved=True,
                actor_resources_before={"ap": caster.ap, "mp": caster.mp},
                actor_resources_after={
                    "ap": result.fight.actors[caster.id].ap,
                    "mp": result.fight.actors[caster.id].mp,
                },
                creation_opcode=delivery["opcode"],
                packet_count=len(result.packets),
                trace=trace,
                attempted_rejections=failures,
                full_client_verified=False,
            )
            if commit_lifecycle:
                exercise_lifecycle(
                    result,
                    actor,
                    character,
                    monster,
                    deck,
                    los,
                    details,
                    runtime_context,
                )
            return details
        details.update(
            status="transaction_rejected",
            attempted_rejections=failures,
            source_preserved=True,
        )
        raise ValueError("All actual empty-cell native7348 candidates rejected")

    def on_runtime(runtime, character, monster, deck, packets, stats):
        runtime_context.update(
            runtime=runtime,
            stats=stats,
            captured_commit_callback=captured_commit_callback,
        )
        return on_ready(runtime.fight, character, monster, deck, packets)

    with patch.object(ready_audit.fixture_module, "fixture", owned_fixture):
        report = ready_audit.run(
            output,
            cases_override=[(2, 153, None)],
            on_ready=None if commit_lifecycle else on_ready,
            on_runtime=on_runtime if commit_lifecycle else None,
            turn_cycle=True,
            turn_steps=1,
        )
    # Preserve failure details too: Ready's catch retains the actual failing stage.
    report["owned_captured_transaction"] = details
    report["audit_tool_sha256"] = hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest()
    report["audit_tool_source_stable"] = report["audit_tool_sha256"] == tool_before
    report["source_stable"] = (
        report["source_stable"] and report["audit_tool_source_stable"]
    )
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, default=str) + "\n"
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--commit-lifecycle", action="store_true")
    args = parser.parse_args()
    report = run(args.output, commit_lifecycle=args.commit_lifecycle)
    print(
        json.dumps(
            {
                "rows": [(row["status"], row.get("reason")) for row in report["rows"]],
                "transaction": report["owned_captured_transaction"].get("status"),
                "source_stable": report["source_stable"],
            }
        )
    )
