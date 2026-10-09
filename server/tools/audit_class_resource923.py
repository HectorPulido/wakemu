#!/usr/bin/env python3
"""Actual Iop Ready grant8405 resource923 action, without fabricated resources."""
import argparse
from contextlib import contextmanager
import json
import copy
import random
import struct
from pathlib import Path
from unittest.mock import patch
import audit_ready_start as ready
import audit_class_normal_casts as normal
import class_spell_eligible_targets as targets
from wakfu_server.spells import available_spells, ACTIVE_SLOT_LEVELS


@contextmanager
def observe_payments(rows):
    original = normal.prepare_server_spell

    def observed(*args, **kwargs):
        fight = args[3]
        actor_id = args[1]["id"]
        actor = fight.actors[actor_id]
        before = dict(ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4])
        result = original(*args, **kwargs)
        actor = result.fight.actors[actor_id]
        rows.append(
            dict(
                stage="prepared_preview",
                level=args[1]["level"],
                target=list(result.plan["target"]),
                costs=result.plan["costs"],
                before=before,
                after=dict(ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4]),
                native_events=[
                    event
                    for event in result.fight.events
                    if event.get("sequence", -1)
                    > (fight.events[-1].get("sequence", -1) if fight.events else -1)
                ],
                packets=[opcode for opcode, payload in result.packets],
                summoned_profiles_after=[
                    source.get("ref")
                    for item in result.fight.actors.values()
                    if isinstance(
                        source := getattr(item, "native_summon_source", None), dict
                    )
                ],
                area_references_after=[
                    row.get("reference")
                    for row in getattr(result.fight, "native_effect_areas", {}).values()
                ],
            )
        )
        return result

    original_candidates = targets.candidate_cells

    def free_candidates(fight, actor_id, *, limit=256):
        from wakfu_server.combat_qi_fight import current_registry

        cells, total = original_candidates(fight, actor_id, limit=4096)
        qi = current_registry(fight).snapshot()
        area_cells = {
            tuple(row["cell"])
            for row in getattr(fight, "native_effect_areas", {}).values()
        }
        # Search order only: every cell still passes the actual cast validator.
        cells = tuple(
            sorted(cells, key=lambda cell: bool(qi.U(*cell[:2])) or cell in area_cells)
        )
        return cells[:limit], total

    with patch.object(normal, "prepare_server_spell", observed), patch.object(
        targets, "candidate_cells", free_candidates
    ):
        yield


class ResourceLifecycleAudit(normal.NormalCastAudit):
    """Extend the committed owned action on a private production runtime."""

    def __call__(
        self, runtime, character, monster, deck, initial_packets, stats_serializer
    ):
        self.owner_source = character, monster, deck
        return super().__call__(
            runtime, character, monster, deck, initial_packets, stats_serializer
        )

    def commit_prepared(
        self, baseline, transaction, stats_serializer, actor_id, new_families
    ):
        initial = super().commit_prepared(
            baseline, transaction, stats_serializer, actor_id, new_families
        )
        branch = copy.deepcopy(baseline)
        normal.commit_spell_transaction(
            branch, copy.deepcopy(transaction), stats_serializer=stats_serializer
        )
        character, monster, deck = self.owner_source
        stages = []
        initial["resource923_lifecycle"] = stages

        def observed_state():
            current = branch.fight.actors[actor_id]
            return dict(
                ap=current.ap,
                mp=current.mp,
                wp=current.effect_stats[4],
                actor_position=list(current.position),
                state_ledgers=normal.actual_state_ledgers(branch.fight),
                actor_ids=list(branch.fight.actors),
                summon_profiles={
                    str(identity): getattr(actor, "native_summon_source", {}).get("ref")
                    for identity, actor in branch.fight.actors.items()
                },
                area_references={
                    str(identity): row["reference"]
                    for identity, row in getattr(
                        branch.fight, "native_effect_areas", {}
                    ).items()
                },
                native_resources=copy.deepcopy(
                    getattr(branch.fight, "native_spell_usage", None)
                ),
            )

        def owned_attempt(reference, label):
            stage = dict(
                stage=label, spell=reference, before=observed_state(), attempts=[]
            )
            stages.append(stage)
            grant = normal.granted_spells(branch.fight, actor_id).get(reference)
            uid = grant["uid"] if grant else (actor_id << 32) | reference
            factory, adapter = normal.server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
                rng=random.Random(17),
            )

            def los(origin, target, preview):
                return normal.authoritative_visible(
                    preview.map_id,
                    origin,
                    target,
                    preview,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in preview.actors.values()
                        if actor.hp > 0
                    },
                )

            try:
                selection = normal.eligible_cast_targets(
                    branch.fight,
                    character,
                    deck,
                    uid,
                    adapter=adapter,
                    line_of_sight=los,
                    actor_id=actor_id,
                    limit=64,
                    maximum_eligible=1,
                )
                stage["target_selection"] = dict(
                    selection,
                    eligible=[
                        dict(target=row["target"]) for row in selection["eligible"]
                    ],
                )
                if not selection["eligible"]:
                    stage.update(status="no_legal_target", after=observed_state())
                    return
                cell = selection["eligible"][0]["target"]
                trace = []
                with normal.combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=4096
                ):
                    prepared = normal.prepare_server_spell(
                        struct.pack(">qqiih", actor_id, uid, *cell),
                        character,
                        {monster["id"]: monster},
                        branch.fight,
                        branch.fight.actors[actor_id].owner_id,
                        deck,
                        action_id=branch.action_id + 1,
                        line_of_sight=los,
                        critical=False,
                        rng=random.Random(17),
                    )
                    packets = normal.commit_spell_transaction(
                        branch, prepared, stats_serializer=stats_serializer
                    )
                stage.update(
                    status="committed",
                    target=list(cell),
                    costs=prepared.plan["costs"],
                    packet_count=len(packets),
                    trace=trace,
                    after=observed_state(),
                )
            except Exception as error:
                stage.update(
                    status="rejected", reason=str(error), after=observed_state()
                )

        owned_attempt(8405, "same_turn_owned_recast")
        stage = dict(
            stage="ordinary_end_ack_start", before=observed_state(), boundaries=[]
        )
        stages.append(stage)
        try:
            for index in range(max(2, len(branch.fight.order) * 2)):
                if (
                    index
                    and branch.fight.current is not None
                    and branch.fight.current.id == actor_id
                    and branch.awaiting_ack is None
                ):
                    break
                if branch.awaiting_ack is not None:
                    pending = branch.awaiting_ack
                    packets = branch.acknowledge_turn(struct.pack(">i", pending))
                    stage["boundaries"].append(
                        dict(actor=None, ack=pending, packet_count=len(packets))
                    )
                    continue
                current = branch.fight.current
                if current is None or branch.fight.phase != "active":
                    raise ValueError("Actual fight ended before the next owned turn")
                packets = (
                    branch.end_turn(current.owner_id, current.id, current.turn_count)
                    if current.controlled
                    else branch.end_server_turn(current.id, branch.fight.turn_id)
                )
                pending = branch.awaiting_ack
                if pending is not None:
                    packets += branch.acknowledge_turn(struct.pack(">i", pending))
                stage["boundaries"].append(
                    dict(actor=current.id, ack=pending, packet_count=len(packets))
                )
            else:
                raise ValueError(
                    "Bounded ordinary timeline did not reach the next owned turn"
                )
            stage.update(status="next_owned_turn", after=observed_state())
        except Exception as error:
            stage.update(status="blocked", reason=str(error), after=observed_state())
            return initial
        owned_attempt(8405, "next_turn_owned_recast")
        # Use a legitimate active deck action as control; its guards are never
        # disabled, and failure remains evidence rather than a forced outcome.
        active = normal.validate_deck(deck, character["breed"], character["level"])[
            "active"
        ]
        if any(active):
            owned_attempt(
                next(reference for reference in active if reference),
                "ordinary_owned_deck_control",
            )
        initial["next_owned_turn_resources_verified"] = (
            stage["status"] == "next_owned_turn"
        )
        return initial


def run(output):
    payments = []
    inspector = ResourceLifecycleAudit(
        candidate_limit=64,
        maximum_eligible=1,
        action_selector=lambda actions: [
            row for row in actions if row["reference"] == 8405
        ],
    )

    def deck(breed, level, passive):
        capacity = sum(level >= threshold for threshold in ACTIVE_SLOT_LEVELS)
        return sorted(
            row["id"]
            for row in available_spells(breed, level)
            if row["kind"] == "active"
        )[:capacity]

    with observe_payments(payments):
        result = ready.run(
            output,
            basics_only=True,
            turn_cycle=True,
            turn_steps=0,
            cases_override=[(8, 36, None), (8, 200, None)],
            active_deck_provider=deck,
            on_runtime=inspector,
        )
    for row in result["rows"]:
        access = row.get("runtime_access", {})
        actual = []
        for action in access.get("actions", []):
            if action.get("reference") != 8405:
                continue
            for attempt in action.get("attempts", []):
                trace = attempt.get("trace", [])
                requested_executed = any(
                    event.get("effect_reference") == 397441
                    and event.get("effect_class") == 923
                    and event.get("status") == "completed"
                    for event in trace
                )
                commit = attempt.get("representative_commit", {})
                preview = next(
                    (
                        payment
                        for payment in payments
                        if payment["level"] == row["level"]
                        and payment["target"] == list(attempt.get("target", ()))
                    ),
                    None,
                )
                creation_observed = (
                    preview is not None
                    and 3793 in preview["summoned_profiles_after"]
                    and bool({889, 2042} & set(preview["area_references_after"]))
                )
                status = (
                    "requested_branch_committed"
                    if requested_executed
                    and creation_observed
                    and commit.get("status") == "committed"
                    else "requested_branch_preview_only"
                    if requested_executed
                    else "not_requested_branch"
                    if attempt.get("prepared")
                    else "rejected"
                )
                actual.append(
                    dict(
                        target=attempt.get("target"),
                        status=status,
                        original923_executed=requested_executed,
                        native_creation_observed=creation_observed,
                        preview_resources=None
                        if preview is None
                        else {
                            key: preview[key] for key in ("before", "after", "costs")
                        },
                        committed_resources=commit.get("resources_after"),
                        commit_status=commit.get("status"),
                    )
                )
        row["resource923_attempts"] = actual
        row["resource923_verified"] = any(
            item["status"] == "requested_branch_committed" for item in actual
        )
    result.update(
        scope="Actual owned Iop Ready grant8405; legal target and real resource payment application",
        payment_previews=payments,
        preview_and_commit_separate=True,
        next_turn_replenishment_verified=False,
        next_turn_lifecycle_attempted=True,
        candidate_order_policy="prefer actual QI/Qs empty cells, preserve native validation",
        requested_action=8405,
        requested_family=923,
        requested_original_effect=397441,
        gameplay_verified=False,
        source_grant=dict(
            effect=397463,
            criterion='not HasEffectWithActionId("caster", 933) and GetInstanceId() <> 862 and GetLevel("caster") >= 36',
        ),
    )
    Path(output).write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    run(args.output)
