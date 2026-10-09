"""Offline actual granted8559 commit, plus labelled eZw ratio stress fixtures.

Ratios33/50 are constructor mechanics fixtures: the installed class root413075
has no parameters and defaults to100. No production definition is modified.
"""
import argparse
from copy import deepcopy
import json
from pathlib import Path
import random
import struct
from unittest.mock import patch

import audit_ready_start as ready_audit
from audit_class_normal_casts import root_failure
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_character_copy_handler import NativeCharacterCopyHandler
from wakfu_server.combat_copied_pa import copied_raw_current
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.combat_hp_raw import hp_raw_current
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_snapshot_wire import snapshot_characteristics
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import available_spells


def _facts(actor):
    return dict(
        actor_id=actor.id,
        hp=actor.hp,
        max_hp=actor.max_hp,
        raw_hp=hp_raw_current(actor),
        raw_ap=copied_raw_current(actor, 2),
        raw_mp=copied_raw_current(actor, 3),
        stats=actor.effect_stats,
        source=actor.native_copy_pa_source,
        wire_hex=snapshot_characteristics(actor).hex(),
    )


class CopyAudit:
    def __call__(
        self, runtime, character, monster, deck, initial_packets, stats_serializer
    ):
        original = snapshot(runtime.fight)
        baseline = deepcopy(runtime)
        for _ in range(max(2, len(baseline.fight.actors) * 4)):
            if baseline.awaiting_ack is not None:
                baseline.acknowledge_turn(struct.pack(">i", baseline.awaiting_ack))
                continue
            current = baseline.fight.current
            if current is not None and current.id == character["id"]:
                break
            if current is None or baseline.fight.phase != "active":
                raise ValueError("Missing actual owned copy caster turn")
            if current.controlled:
                baseline.end_turn(current.owner_id, current.id, current.turn_count)
            else:
                baseline.end_server_turn(current.id, baseline.fight.turn_id)
        else:
            raise ValueError("Actual copy caster turn was not reached")
        fight = baseline.fight
        caster = fight.actors[character["id"]]
        grant = grant_record(fight, caster.id, 8559)
        if grant is None:
            raise ValueError("Actual Ready did not grant class spell8559")

        def los(origin, target, current):
            return authoritative_visible(
                current.map_id,
                origin,
                target,
                current,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in current.actors.values()
                    if actor.hp > 0
                },
            )

        _, adapter = server_runtime(
            character,
            {monster["id"]: monster},
            deck,
            action_id=baseline.action_id + 1,
            critical=False,
            rng=random.Random(17),
        )
        selected = eligible_cast_targets(
            fight,
            character,
            deck,
            grant["uid"],
            adapter=adapter,
            line_of_sight=los,
            actor_id=caster.id,
            limit=64,
            maximum_eligible=1,
        )
        if not selected["eligible"]:
            return dict(
                status="no_actual_eligible_copy_target",
                selection=selected,
                source_preserved=snapshot(runtime.fight) == original,
            )
        target = tuple(selected["eligible"][0]["target"])
        rows = []
        native_calculate = NativeCharacterCopyHandler._calculate
        for ratio in (100, 33, 50):
            trace = []
            row = dict(
                ratio=ratio,
                scope=(
                    "actual_native_class8559"
                    if ratio == 100
                    else "mechanic_stress_parameter_override_not_native_class_route"
                ),
            )

            def calculated(handler, effect, values, invocation, runner):
                if ratio != 100:
                    effect = dict(effect, parameters=[float(ratio), 0.0])
                return native_calculate(handler, effect, values, invocation, runner)

            before = snapshot(fight)
            try:
                with patch.object(
                    NativeCharacterCopyHandler, "_calculate", calculated
                ), combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=4096
                ):
                    transaction = prepare_server_spell(
                        struct.pack(">qqiih", caster.id, grant["uid"], *target),
                        character,
                        {monster["id"]: monster},
                        fight,
                        caster.owner_id,
                        deck,
                        action_id=baseline.action_id + 1,
                        line_of_sight=los,
                        critical=False,
                        rng=random.Random(17),
                    )
                created = [
                    actor
                    for uid, actor in transaction.fight.actors.items()
                    if uid not in fight.actors
                    and getattr(actor, "native_copy_pa_source", None) is not None
                ]
                if len(created) != 1:
                    raise ValueError(
                        "Actual1002 transaction did not create exactly one typed copy"
                    )
                copy_actor = created[0]
                row["created"] = deepcopy(_facts(copy_actor))
                branch = deepcopy(baseline)
                packets = commit_spell_transaction(
                    branch, transaction, stats_serializer=stats_serializer
                )
                row["commit"] = dict(
                    packet_count=len(packets), plain_json_snapshot=True
                )
                json.dumps(snapshot(branch.fight), allow_nan=False)
                copy_actor = branch.fight.actors[copy_actor.id]
                row["committed"] = deepcopy(_facts(copy_actor))
                # These are trusted PA mutation boundaries, not fabricated spell requests.
                with branch.fight.effect_resolution():
                    actual = branch.fight.apply_effect_damage(
                        caster.id, copy_actor.id, 10
                    )
                row["damage10"] = dict(
                    actual_raw_delta=actual, **deepcopy(_facts(copy_actor))
                )
                actual = branch.fight.apply_effect_healing(caster.id, copy_actor.id, 1)
                row["heal1"] = dict(
                    actual_raw_delta=actual, **deepcopy(_facts(copy_actor))
                )
                wire = stats_serializer(copy_actor, branch.fight)
                repeated = stats_serializer(copy_actor, branch.fight)
                if wire != repeated:
                    raise AssertionError("Repeated actual copy stats changed bytes")
                json.dumps(snapshot(branch.fight), allow_nan=False)
                row.update(
                    status="committed_and_pa_mutations_serialized",
                    repeated_stats_stable=True,
                )
            except Exception as error:
                row.update(status="rejected", failure=root_failure(error, trace))
            row["trace"] = trace
            row["source_preserved"] = (
                snapshot(fight) == before and snapshot(runtime.fight) == original
            )
            if not row["source_preserved"]:
                raise AssertionError("Copy audit changed its actual Ready source")
            rows.append(row)
        return dict(
            status="actual_copy_and_ratio_stress_audited",
            target=target,
            actual_grant_uid=grant["uid"],
            cases=rows,
            source_preserved=True,
        )


def run(output):
    # Class14's actual innate3769 owns the649 grant8559; no synthetic grant/deck.
    def deck_provider(breed, level, passive):
        return [
            row["id"]
            for row in available_spells(breed, level)
            if row["kind"] == "active"
        ][:12]

    return ready_audit.run(
        output,
        cases_override=[(14, 200, None)],
        active_deck_provider=deck_provider,
        on_runtime=CopyAudit(),
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
