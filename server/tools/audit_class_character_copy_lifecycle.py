"""Actual class8559 creation and allocated-book cast; offline, no services.

The death branch is a separately labelled trusted PA mutation stress case.
It does not claim a class spell caused lethal damage or graphical acceptance.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import struct

import audit_ready_start as ready
from audit_class_normal_casts import root_failure
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_cast import resolve_owned_spell_action
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_hp_raw import hp_raw_current
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.combat_summon_spellbook import actor_action_book
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells


def advance(runtime):
    if runtime.awaiting_ack is not None:
        return runtime.acknowledge_turn(struct.pack(">i", runtime.awaiting_ack))
    actor = runtime.fight.current
    if runtime.fight.phase != "active" or actor is None:
        raise ValueError("Missing active actual lifecycle turn")
    if actor.controlled:
        return runtime.end_turn(actor.owner_id, actor.id, actor.turn_count)
    return runtime.end_server_turn(actor.id, runtime.fight.turn_id)


def reach(runtime, identity, limit=32):
    steps = []
    for _ in range(limit):
        if (
            runtime.awaiting_ack is None
            and not runtime.pending
            and runtime.fight.current is not None
            and runtime.fight.current.id == identity
        ):
            return steps
        before = runtime.fight.current.id if runtime.fight.current else None
        packets = advance(runtime)
        steps.append(
            dict(
                actor_id=before,
                packet_count=len(packets),
                awaiting_ack=runtime.awaiting_ack,
            )
        )
    raise ValueError("Actual copy lifecycle turn was not reached")


class OwnedCopyLifecycle:
    def __call__(
        self, runtime, character, monster, deck, initial_packets, stats_serializer
    ):
        original = snapshot(runtime.fight)
        branch = deepcopy(runtime)
        output = dict(
            scope="actual_native_class8559_owned_copy_lifecycle",
            gameplay_verified=False,
        )
        trace = []

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

        def prepare(actor_id, uid, target, *, runtime_branch=None):
            current_runtime = branch if runtime_branch is None else runtime_branch
            return prepare_server_spell(
                struct.pack(">qqiih", actor_id, uid, *target),
                character,
                {monster["id"]: monster},
                current_runtime.fight,
                character["account_id"],
                deck,
                action_id=current_runtime.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=random.Random(17),
            )

        def select(actor_id, uid):
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
                rng=random.Random(17),
            )
            return eligible_cast_targets(
                branch.fight,
                character,
                deck,
                uid,
                adapter=adapter,
                line_of_sight=los,
                actor_id=actor_id,
                limit=128,
                maximum_eligible=1,
            )

        try:
            output["owner_turns"] = reach(branch, character["id"])
            grant = grant_record(branch.fight, character["id"], 8559)
            if grant is None:
                raise ValueError("Actual Ready did not grant8559")
            selection = select(character["id"], grant["uid"])
            if not selection["eligible"]:
                raise ValueError("Actual8559 has no eligible creation target")
            before_ids = set(branch.fight.actors)
            with combat_diagnostic_scope(lambda **e: trace.append(e), limit=4096):
                transaction = prepare(
                    character["id"],
                    grant["uid"],
                    tuple(selection["eligible"][0]["target"]),
                )
            created = [
                a
                for uid, a in transaction.fight.actors.items()
                if uid not in before_ids and getattr(a, "native_copy_pa_source", None)
            ]
            if len(created) != 1:
                raise ValueError("Actual8559 did not create exactly one typed copy")
            identity = created[0].id
            commit_spell_transaction(
                branch, transaction, stats_serializer=stats_serializer
            )
            output["copy_id"] = identity
            output["copy_turns"] = reach(branch, identity)
            copy_actor = branch.fight.actors[identity]
            book = actor_action_book(copy_actor)
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
            )
            metadata = adapter.actor_authority(branch.fight, copy_actor)
            output["native_identity"] = dict(
                breed_id=metadata.breed_id,
                actor_type=metadata.native_actor_type,
                source_breed=character["breed"],
                controller_id=metadata.native_controller_id,
            )
            output["book"] = book["actions"]
            # Preserve the actual active copied turn for independent PA stress.
            # A legitimate attack can finish combat; do not mutate that result.
            death_source = deepcopy(branch.fight)
            removal_branch = deepcopy(branch)
            expiry_branch = deepcopy(branch)
            attempts = []
            used = None
            for action in book["actions"]:
                row = dict(action)
                selected = select(identity, action["uid"])
                if not selected["eligible"]:
                    row.update(status="no_native_eligible_target", selection=selected)
                    attempts.append(row)
                    continue
                target = tuple(selected["eligible"][0]["target"])
                before = snapshot(branch.fight)
                cast_trace = []
                try:
                    with combat_diagnostic_scope(
                        lambda **e: cast_trace.append(e), limit=4096
                    ):
                        cast = prepare(identity, action["uid"], target)
                    completed = [
                        e
                        for e in cast_trace
                        if e.get("status") == "completed"
                        and e.get("effect_class") not in (330, 400)
                    ]
                    if not completed:
                        row.update(status="prepared_without_completed_leaf")
                        attempts.append(row)
                        continue
                    animation = next(p for op, p in cast.packets if op == 12588)
                    if struct.unpack_from(">qih", animation, 20) != (
                        action["uid"],
                        action["reference"],
                        action["level"],
                    ):
                        raise AssertionError(
                            "Allocated copied action wire identity changed"
                        )
                    if snapshot(branch.fight) != before:
                        raise AssertionError(
                            "Copied action preparation mutated its source"
                        )
                    row.update(
                        status="actual_owned_cast_committed",
                        target=target,
                        costs=cast.plan["costs"],
                        completed_effects=completed,
                        resources_before=dict(copy_actor.effect_stats),
                        resources_after=dict(cast.fight.actors[identity].effect_stats),
                        packet_count=len(
                            commit_spell_transaction(
                                branch, cast, stats_serializer=stats_serializer
                            )
                        ),
                    )
                    used = action
                    attempts.append(row)
                    break
                except Exception as error:
                    row.update(
                        status="rejected", failure=root_failure(error, cast_trace)
                    )
                    attempts.append(row)
            output["owned_cast_attempts"] = attempts
            if used is None:
                raise ValueError("No copied allocated action completed a native effect")
            output["owned_cast_status"] = "actual_owned_copy_cast_verified"
            output["foreign_uid_rejections"] = []
            for uid in (
                (character["id"] << 32) | used["reference"],
                (identity << 32) | used["reference"],
            ):
                before = snapshot(branch.fight)
                try:
                    prepare(identity, uid, branch.fight.actors[identity].position)
                except ValueError as error:
                    output["foreign_uid_rejections"].append(
                        dict(uid=uid, reason=str(error))
                    )
                else:
                    raise AssertionError("Foreign copied action UID was accepted")
                if snapshot(branch.fight) != before:
                    raise AssertionError("Rejected copied action changed its source")
            try:
                death = death_source
                before = snapshot(death)
                actor = death.actors[identity]
                with death.effect_resolution():
                    actual = death.apply_effect_damage(
                        character["id"], identity, hp_raw_current(actor)
                    )
                retired = identity in retired_summon_ids(death)
                if not retired:
                    raise AssertionError(
                        "Actual copied PA death did not retire its owned QK"
                    )
                output["death_stress"] = dict(
                    scope="trusted_PA_lethal_mutation_not_class_spell",
                    actual_raw_damage=actual,
                    retired=True,
                    actor_in_order=identity in death.order,
                    qi_slot=actor.native_obstacle_id,
                    before_actor=before["actors"].get(str(identity)),
                )
                try:
                    resolve_owned_spell_action(
                        dict(actor_id=identity, spell_uid=used["uid"]),
                        character,
                        death,
                        character["account_id"],
                        deck,
                    )
                except ValueError as error:
                    output["death_stress"]["expired_uid_rejection"] = str(error)
                else:
                    raise AssertionError(
                        "Retired copied action UID remained accessible"
                    )
            except Exception as error:
                output["death_stress"] = dict(
                    scope="trusted_PA_lethal_mutation_not_class_spell",
                    status="rejected",
                    failure=root_failure(error, []),
                )
            # Source8559 root413396 eXc explicitly targets an owned2382 copy.
            # Probe the real second owner turn on an independent legal branch;
            # this is a class action removal path, not automatic timer expiry.
            removal_trace = []
            removal_before = None
            try:
                removal_turns = reach(removal_branch, character["id"])
                removal_before = snapshot(removal_branch.fight)
                current_grant = grant_record(
                    removal_branch.fight, character["id"], 8559
                )
                if current_grant is None:
                    raise ValueError("Actual owner turn no longer owns8559")
                own_copy = removal_branch.fight.actors[identity]
                with combat_diagnostic_scope(
                    lambda **e: removal_trace.append(e), limit=4096
                ):
                    removal = prepare(
                        character["id"],
                        current_grant["uid"],
                        own_copy.position,
                        runtime_branch=removal_branch,
                    )
                if snapshot(removal_branch.fight) != removal_before:
                    raise AssertionError("Copy removal preparation changed its source")
                packets = commit_spell_transaction(
                    removal_branch, removal, stats_serializer=stats_serializer
                )
                old_copy = removal_branch.fight.actors[identity]
                output["native_class_removal"] = dict(
                    scope="actual8559_recast_owned_copy_not_timer_expiry",
                    status="actual_class_action_committed",
                    owner_turns=removal_turns,
                    target_id=identity,
                    target_position=list(own_copy.position),
                    costs=removal.plan["costs"],
                    packet_count=len(packets),
                    hp=old_copy.hp,
                    qi_slot=old_copy.native_obstacle_id,
                    retired=identity in retired_summon_ids(removal_branch.fight),
                    completed_effects=[
                        e for e in removal_trace if e.get("status") == "completed"
                    ],
                )
                try:
                    resolve_owned_spell_action(
                        dict(actor_id=identity, spell_uid=used["uid"]),
                        character,
                        removal_branch.fight,
                        character["account_id"],
                        deck,
                    )
                except ValueError as error:
                    output["native_class_removal"]["old_uid_rejection"] = str(error)
                else:
                    output["native_class_removal"]["old_uid_status"] = "still_owned"
            except Exception as error:
                output["native_class_removal"] = dict(
                    scope="actual8559_recast_owned_copy_not_timer_expiry",
                    status="rejected",
                    failure=root_failure(error, removal_trace),
                    preparation_source_preserved=(
                        removal_before is None
                        or snapshot(removal_branch.fight) == removal_before
                    ),
                )
            stages = []
            for _ in range(24):
                if (
                    expiry_branch.fight.phase != "active"
                    or identity in retired_summon_ids(expiry_branch.fight)
                ):
                    break
                before = expiry_branch.fight.current.id
                packets = advance(expiry_branch)
                stages.append(dict(actor_id=before, packet_count=len(packets)))
            output["expiry"] = dict(
                scope="actual_turn_cycles_from_pre_attack_owned_copy_turn",
                actual_turn_stages=stages,
                retired=identity in retired_summon_ids(expiry_branch.fight),
                status=(
                    "retired_in_actual_turn_cycles"
                    if identity in retired_summon_ids(expiry_branch.fight)
                    else (
                        "combat_finished_before_expiry_observation"
                        if expiry_branch.fight.phase != "active"
                        else "not_retired_in_bounded_actual_turn_cycles"
                    )
                ),
            )
            json.dumps(snapshot(branch.fight), allow_nan=False)
            output["status"] = "actual_owned_copy_cast_verified"
            output["post_cast_phase"] = branch.fight.phase
        except Exception as error:
            if output.get("owned_cast_status") == "actual_owned_copy_cast_verified":
                output.update(
                    status="actual_owned_copy_cast_verified",
                    followup_failure=root_failure(error, trace),
                )
            else:
                output.update(status="rejected", failure=root_failure(error, trace))
        output["source_preserved"] = snapshot(runtime.fight) == original
        if not output["source_preserved"]:
            raise AssertionError("Lifecycle audit mutated actual Ready source")
        return output


def run(output):
    return ready.run(
        output,
        cases_override=[(14, 200, None)],
        active_deck_provider=lambda breed, level, passive: [
            s["id"] for s in available_spells(breed, level) if s["kind"] == "active"
        ][:12],
        on_runtime=OwnedCopyLifecycle(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    run(parser.parse_args().output)
