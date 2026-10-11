"""Bounded real4603 creation, occupied-cell rejection and legal action lifetime.

No HP/stat injection: absence of a lethal legal action is an explicit gap.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import struct

import audit_ready_start as ready
from audit_class_character_copy_lifecycle import advance, reach
from audit_class_normal_casts import root_failure
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_summon_retirement import retired_summon_ids
from wakfu_server.fight_checkpoint_store import snapshot

DECK = [4581, 4583, 4584, 4585, 4586, 4587, 4588, 4589, 4590, 4592, 4593, 8481]


class DoubleLifecycle:
    def __call__(self, runtime, character, monster, deck, packets, stats):
        original = snapshot(runtime.fight)
        branch = deepcopy(runtime)
        output = dict(
            scope="actual_class4603_legal_action_lifecycle",
            client_verified=False,
            hp_injection=False,
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

        def prepare(uid, target):
            return prepare_server_spell(
                struct.pack(">qqiih", character["id"], uid, *target),
                character,
                {monster["id"]: monster},
                branch.fight,
                character["account_id"],
                deck,
                action_id=branch.action_id + 1,
                line_of_sight=los,
                critical=False,
                rng=random.Random(17),
            )

        try:
            output["owner_turns"] = reach(branch, character["id"])
            grant = grant_record(branch.fight, character["id"], 4603)
            if grant is None:
                raise ValueError("Normal Ready did not grant Double4603")
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
            )
            selected = eligible_cast_targets(
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
            output["selection"] = selected
            if not selected["eligible"]:
                raise ValueError("No actual eligible Double target")
            before_ids = set(branch.fight.actors)
            with combat_diagnostic_scope(lambda **e: trace.append(e), limit=4096):
                creation = prepare(
                    grant["uid"], tuple(selected["eligible"][0]["target"])
                )
            created = set(creation.fight.actors) - before_ids
            if len(created) != 1:
                raise ValueError("Double creation did not produce exactly one actor")
            identity = created.pop()
            output["creation"] = dict(
                actor_id=identity,
                costs=creation.plan["costs"],
                packet_count=len(
                    commit_spell_transaction(branch, creation, stats_serializer=stats)
                ),
            )
            # Return to a real resourced owner turn before checking occupancy.
            advance(branch)
            output["next_owner_turns"] = reach(branch, character["id"])
            before = snapshot(branch.fight)
            try:
                prepare(grant["uid"], branch.fight.actors[identity].position)
            except ValueError as error:
                output["occupied_cell"] = root_failure(error)
                if getattr(error, "native_casting_result", None) not in {
                    "twE",
                    "twF",
                    "twG",
                    "twH",
                    "twI",
                    "twJ",
                    "twT",
                    "twU",
                    "twV",
                    "twX",
                    "twY",
                }:
                    raise
            else:
                raise AssertionError("Occupied Double cell was accepted")
            if snapshot(branch.fight) != before:
                raise AssertionError("Rejected occupied cast changed actual source")
            output["occupied_cell"]["source_preserved"] = True
            # Jugarreta requires an actual living Double; the baseline without one
            # correctly rejects its native HasSummonWithBreed criterion.
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
            )
            swap_uid = (character["id"] << 32) | 8481
            selection = eligible_cast_targets(
                branch.fight,
                character,
                deck,
                swap_uid,
                adapter=adapter,
                line_of_sight=los,
                actor_id=character["id"],
                limit=128,
                maximum_eligible=1,
            )
            output["jugarreta_selection"] = selection
            if not selection["eligible"]:
                raise ValueError(
                    "Actual living Double did not enable legal Jugarreta context"
                )
            with combat_diagnostic_scope(lambda **e: trace.append(e), limit=4096):
                swap = prepare(swap_uid, tuple(selection["eligible"][0]["target"]))
                output["jugarreta"] = dict(
                    costs=swap.plan["costs"],
                    packet_count=len(
                        commit_spell_transaction(branch, swap, stats_serializer=stats)
                    ),
                )
            attempts = []
            for cycle in range(4):
                if (
                    identity in retired_summon_ids(branch.fight)
                    or branch.fight.phase != "active"
                ):
                    break
                reach(branch, character["id"])
                for reference in DECK:
                    before = snapshot(branch.fight)
                    target = branch.fight.actors[identity].position
                    try:
                        cast = prepare((character["id"] << 32) | reference, target)
                        hp_before = branch.fight.actors[identity].hp
                        hp_after = cast.fight.actors[identity].hp
                        row = dict(
                            cycle=cycle,
                            reference=reference,
                            hp_before=hp_before,
                            hp_after=hp_after,
                        )
                        if hp_after < hp_before:
                            row["packet_count"] = len(
                                commit_spell_transaction(
                                    branch, cast, stats_serializer=stats
                                )
                            )
                            row["status"] = "legal_class_damage_committed"
                        else:
                            row["status"] = "legal_preview_without_double_hp_loss"
                        attempts.append(row)
                    except Exception as error:
                        if snapshot(branch.fight) != before:
                            raise AssertionError(
                                "Failed legal damage attempt changed source"
                            )
                        attempts.append(
                            dict(
                                cycle=cycle,
                                reference=reference,
                                status="rejected",
                                failure=root_failure(error),
                            )
                        )
                    if identity in retired_summon_ids(branch.fight):
                        break
                if identity not in retired_summon_ids(branch.fight):
                    advance(branch)
            output["legal_damage_attempts"] = attempts
            output["retired"] = identity in retired_summon_ids(branch.fight)
            actor = branch.fight.actors[identity]
            output["final"] = dict(
                hp=actor.hp,
                qi_slot=actor.native_obstacle_id,
                in_order=identity in branch.fight.order,
                checkpoint_json_valid=True,
            )
            json.dumps(snapshot(branch.fight), allow_nan=False)
            lethal = any(
                row.get("status") == "legal_class_damage_committed"
                and row.get("hp_after") == 0
                for row in attempts
            )
            output["status"] = (
                "actual_class_death_retirement_verified"
                if output["retired"] and lethal
                else "actual_turn_retirement_verified_death_unresolved"
                if output["retired"]
                else "creation_negative_verified_legal_lethal_context_unresolved"
            )
        except Exception as error:
            output.update(status="rejected", failure=root_failure(error, trace))
        output["source_preserved"] = snapshot(runtime.fight) == original
        if not output["source_preserved"]:
            raise AssertionError("Double lifecycle audit changed Ready source")
        return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    ready.run(
        args.output,
        cases_override=[(4, 100, 4606)],
        active_deck_provider=lambda *_: DECK,
        on_runtime=DoubleLifecycle(),
    )
