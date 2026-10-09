"""Paired constructor source fixtures: persisted currentTitle, no PA injection.

The title operand is a source fixture, not a claim that a cosmetic is unlocked
on a user's account. Actual PJ consumes its item definition independently.
"""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import struct

import audit_ready_start as ready
from audit_class_character_copy_lifecycle import reach
from audit_class_normal_casts import root_failure
from audit_sram_double_lifecycle import DECK
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells

TITLE = 2822  # Original item19317: family20, native level0, maximum HP +200.


class PositiveTitleAudit:
    def __call__(self, runtime, character, monster, deck, packets, stats):
        before = snapshot(runtime.fight)
        branch = deepcopy(runtime)
        action = 4603 if character["breed"] == 4 else 8559
        title = character["appearance"]["currentTitle"]
        output = dict(
            scope="persisted_currentTitle_constructor_source_fixture",
            action=action,
            title_operand=title,
            cosmetic_unlock_verified=False,
            hp_injection=False,
            inventory_injection=False,
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

        try:
            output["turns"] = reach(branch, character["id"])
            grant = grant_record(branch.fight, character["id"], action)
            if grant is None:
                raise ValueError("Actual Ready did not grant constructor action")
            _, adapter = server_runtime(
                character,
                {monster["id"]: monster},
                deck,
                action_id=branch.action_id + 1,
                critical=False,
            )
            source = adapter.actor_authority(
                branch.fight, branch.fight.actors[character["id"]]
            )
            if source.native_selected_cosmetics[7] != title:
                raise AssertionError(
                    "Preplacement currentTitle did not produce actual authority"
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
            output["selection"] = selection
            if not selection["eligible"]:
                raise ValueError("No actual legal copied constructor target")
            identities = set(branch.fight.actors)
            with combat_diagnostic_scope(lambda **e: trace.append(e), limit=4096):
                cast = prepare_server_spell(
                    struct.pack(
                        ">qqiih",
                        character["id"],
                        grant["uid"],
                        *selection["eligible"][0]["target"]
                    ),
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
            created = set(cast.fight.actors) - identities
            if len(created) != 1:
                raise ValueError("Constructor did not produce exactly one actor")
            identity = created.pop()
            output["packet_count"] = len(
                commit_spell_transaction(branch, cast, stats_serializer=stats)
            )
            actor = branch.fight.actors[identity]
            output.update(
                status="actual_constructor_committed",
                actor_id=identity,
                hp=actor.hp,
                max_hp=actor.max_hp,
                raw_characteristics=dict(actor.effect_stats),
                equipment_calls=getattr(actor, "native_applied_equipment_calls", []),
                equipment_source=getattr(
                    actor, "native_character_copy_equipment_source", None
                ),
                checkpoint_json_valid=True,
            )
            json.dumps(snapshot(branch.fight), allow_nan=False)
            if title and (
                len(output["equipment_calls"]) != (2 if action == 4603 else 1)
                or any(
                    call["roots"] != [19317] or call["native_ps"] is not None
                    for call in output["equipment_calls"]
                )
            ):
                raise AssertionError("Actual ordered PJ item/self/nullPS calls absent")
        except Exception as error:
            output.update(status="rejected", failure=root_failure(error, trace))
        output["trace"] = trace
        output["source_preserved"] = snapshot(runtime.fight) == before
        if not output["source_preserved"]:
            raise AssertionError("Constructor source fixture mutated Ready runtime")
        return output


def run(output):
    operands = iter((0, TITLE, 0, TITLE))

    def character_source(character, *_):
        if character.get("inventory_items"):
            raise ValueError("Positive title fixture requires existing empty inventory")
        character["appearance"]["currentTitle"] = next(operands)

    def deck_provider(breed, level, passive):
        return (
            DECK
            if breed == 4
            else [
                s["id"] for s in available_spells(breed, level) if s["kind"] == "active"
            ][:12]
        )

    result = ready.run(
        output,
        cases_override=[
            (4, 100, 4606),
            (4, 100, 4606),
            (14, 200, None),
            (14, 200, None),
        ],
        active_deck_provider=deck_provider,
        preplacement_character_fixture_provider=character_source,
        on_runtime=PositiveTitleAudit(),
    )
    comparisons = []
    for left, right, expected in ((0, 1, 0), (2, 3, 200)):
        baseline = result["rows"][left]["runtime_access"]
        positive = result["rows"][right]["runtime_access"]
        committed = all(
            row.get("status") == "actual_constructor_committed"
            for row in (baseline, positive)
        )
        delta = positive["max_hp"] - baseline["max_hp"] if committed else None
        comparisons.append(
            dict(
                action=baseline["action"],
                expected_native_max_hp_delta=expected,
                actual_max_hp_delta=delta,
                verified=committed and delta == expected,
                source_order=(
                    "two_PJ_calls_then_state3667_eYO_forced_HP_maximum"
                    if baseline["action"] == 4603
                    else "one_PJ_call_after_copied_PA_initialization"
                ),
            )
        )
    result["paired_constructor_comparisons"] = comparisons
    result["helper_sha256"] = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    result["cosmetic_unlock_verified"] = False
    output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
