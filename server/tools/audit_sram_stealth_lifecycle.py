"""Actual Ready grant4604 -> normal cast -> legal attack -> real turn/ACK."""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import struct

import audit_ready_start as ready
from audit_class_character_copy_lifecycle import advance, reach
from audit_class_normal_casts import actual_state_ledgers, root_failure
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_server_spell import server_runtime, prepare_server_spell
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot


DECK = [4579, 4581, 4583, 4584, 4585, 4586, 4587, 4588, 4589, 4590, 4592, 4593]


class StealthLifecycle:
    def __init__(self, scenario="stealth"):
        if scenario not in ("stealth", "resources"):
            raise ValueError("Unknown Sram lifecycle scenario")
        self.scenario = scenario

    def __call__(self, runtime, character, monster, deck, initial_packets, stats):
        original = snapshot(runtime.fight)
        branch = deepcopy(runtime)
        trace = []
        result = dict(
            scope="actual_sram4604_cast_attack_turn_lifecycle",
            client_verified=False,
            state_injection=False,
            resource_injection=False,
            stages=[],
        )

        def facts():
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
                rng=random.Random(17),
            )
            actor = branch.fight.actors[character["id"]]
            return dict(
                states=actual_state_ledgers(branch.fight),
                fight_properties=sorted(
                    adapter.actor_authority.properties(branch.fight, actor)
                ),
                ap=actor.ap,
                mp=actor.mp,
                wp=actor.effect_stats[4],
                current=None
                if branch.fight.current is None
                else branch.fight.current.id,
            )

        def los(a, b, fight):
            return authoritative_visible(
                fight.map_id,
                a,
                b,
                fight,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in fight.actors.values()
                    if actor.hp > 0
                },
            )

        def cast(uid, target):
            before = facts()
            with combat_diagnostic_scope(
                lambda **event: trace.append(event), limit=8192
            ):
                tx = prepare_server_spell(
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
                packets = commit_spell_transaction(branch, tx, stats_serializer=stats)
            result["stages"].append(
                dict(
                    kind="normal_cast",
                    uid=uid,
                    target=target,
                    costs=tx.plan["costs"],
                    before=before,
                    after=facts(),
                    packets=len(packets),
                    diagnostics=tx.plan.get("cast_diagnostics"),
                )
            )

        try:
            result["initial_turns"] = reach(branch, character["id"])
            result["before_stealth"] = facts()
            if self.scenario == "resources":
                # Native owned attacks: build WeakPoint, apply Hemorrhage,
                # then exercise the positional finisher/consumption branch.
                # Observe actual state levels; never install a threshold.
                for reference in (4579, 4588, 4594):
                    uid = (character["id"] << 32) | reference
                    for attempt in range(2):
                        try:
                            cast(uid, branch.fight.actors[monster["id"]].position)
                            break
                        except Exception as error:
                            result.setdefault("resource_attempt_failures", []).append(
                                dict(
                                    reference=reference,
                                    attempt=attempt,
                                    failure=root_failure(error, trace),
                                )
                            )
                            if attempt == 0 and branch.fight.phase == "active":
                                advance(branch)
                                reach(branch, character["id"])
                result["after_resources"] = facts()
                result[
                    "status"
                ] = "actual_resource_sequence_observed_not_all_thresholds_verified"
                return result
            grant = grant_record(branch.fight, character["id"], 4604)
            if grant is None:
                raise ValueError("Actual Ready did not grant invisibility4604")
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
                rng=random.Random(17),
            )
            selected = eligible_cast_targets(
                branch.fight,
                character,
                deck,
                grant["uid"],
                adapter=adapter,
                line_of_sight=los,
                limit=256,
                maximum_eligible=1,
            )
            result["stealth_selection"] = selected
            if not selected["eligible"]:
                raise ValueError("No legal original invisibility target")
            cast(grant["uid"], tuple(selected["eligible"][0]["target"]))
            # Independent quiet branch tests timers without triggering damage reveal.
            attack_branch = branch
            branch = deepcopy(branch)
            advance(branch)
            reach(branch, character["id"])
            result["quiet_after_first_owner_turn"] = facts()
            advance(branch)
            reach(branch, character["id"])
            result["quiet_after_second_owner_turn"] = facts()
            branch = attack_branch
            # Attack the actual enemy, not a fabricated/empty success target.
            attack_uid = (character["id"] << 32) | 4579
            try:
                cast(attack_uid, branch.fight.actors[monster["id"]].position)
            except Exception as error:
                result["attack_failure"] = root_failure(error, trace)
            result["after_attack"] = facts()
            result["end_packets"] = len(advance(branch))
            result["return_turns"] = reach(branch, character["id"])
            result["after_next_owner_turn"] = facts()
            initial = result["stages"][0]["after"]
            if not {5, 54}.issubset(initial["fight_properties"]):
                raise AssertionError(
                    "Original invisibility failed to install its two properties"
                )
            first = result["quiet_after_first_owner_turn"]["fight_properties"]
            second = result["quiet_after_second_owner_turn"]
            if 5 not in first or 54 in first:
                raise AssertionError(
                    "Native one-end property timer diverged from two-end invisibility"
                )
            if 5 in second["fight_properties"] or 54 in second["fight_properties"]:
                raise AssertionError(
                    "Quiet two-end expiration left an invisible property"
                )

            def owner_entries(observation):
                states = observation["states"]
                owner = states.get(character["id"], states.get(str(character["id"])))
                if owner is None:
                    raise AssertionError("Missing authoritative owner state ledger")
                return owner["entries"]

            if any(entry["reference"] == 3129 for entry in owner_entries(second)):
                raise AssertionError(
                    "Quiet two-end invisibility state survived actual expiration"
                )
            if result.get("attack_failure") is not None:
                raise AssertionError("The actual enemy attack did not commit")
            completed = {
                row.get("effect_reference")
                for row in trace
                if row.get("status") == "completed"
            }
            result["damage_reveal_completed_children"] = sorted(
                completed & {410579, 411072, 411073}
            )
            if not {410579, 411072, 411073}.issubset(completed):
                raise AssertionError(
                    "Actual paid attack did not execute native cost/damage reveal chain"
                )
            if 5 in result["after_attack"]["fight_properties"]:
                raise AssertionError("Native damage reveal left property5 installed")
            if any(
                entry["reference"] == 3129
                for entry in owner_entries(result["after_attack"])
            ):
                raise AssertionError("Native damage reveal left state3129 installed")
            result["verified_contracts"] = [
                "native_initial_property_5_and_54",
                "independent_quiet_one_end_property_54_expiry",
                "independent_quiet_two_end_state_3129_and_property_5_expiry",
                "actual_paid_attack_cost_group_and_damage_listener_remove_invisibility",
            ]
            result["status"] = "native_bounded_stealth_lifecycle_verified"
            result["unverified_contracts"] = [
                "enemy_client_visibility",
                "movement_disclosure",
            ]
            json.dumps(snapshot(branch.fight), allow_nan=False)
        except Exception as error:
            result.update(status="rejected", failure=root_failure(error, trace))
        finally:
            result["trace"] = trace
            result["source_preserved"] = snapshot(runtime.fight) == original
            if not result["source_preserved"]:
                raise AssertionError("Sram lifecycle audit mutated Ready baseline")
        return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--scenario", choices=("stealth", "resources"), default="stealth"
    )
    args = parser.parse_args()
    ready.run(
        args.output,
        cases_override=[(4, 200, None)],
        active_deck_provider=lambda *_: DECK,
        on_runtime=StealthLifecycle(args.scenario),
        turn_cycle=True,
        turn_steps=1,
        monster_reference=5574,
        monster_level=133,
    )
