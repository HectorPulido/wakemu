#!/usr/bin/env python3
"""Find a legal M2 preparation sequence through owned casting and real turns."""
import copy
import argparse
import json
import random
import struct
from pathlib import Path

import audit_active_spells as audit
from wakfu_server.combat_actor import (
    actual_actor_stats,
    actual_monster_actor_stats,
    actor_effects,
)
from wakfu_server.combat_ready import prepare_ready
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_spell_grant import granted_spells
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_native_los_ray import cast_rays
from wakfu_server.spells import encode_deck
from audit_class_summon_reactions import actor_summary, native_event_trace


def run(output, blocking_fixture=False):
    hashes = audit.init.source_hashes()
    source, target = (
        ((-7, -7, -1), (-7, 0, -1))
        if blocking_fixture
        else ((-8, -7, -1), (-14, -7, -1))
    )
    precision_cell = (-13, -7, -1) if blocking_fixture else target
    wall_cell = target if blocking_fixture else (-8, -1, -1)
    terrain = audit.bounded_arena(audit.map_geometry(1134), source, [target], radius=12)
    deck = encode_deck([4810, 4813, 4816, 4820])
    rows = []
    # These are candidate legal actions, never injected state outcomes.
    for prefix in ((), (7752,)):
        character, creature, fight = audit.fixture(
            9,
            20,
            target,
            terrain,
            source,
            ready=False,
            monster_reference=5574,
            monster_level=133,
        )
        rng = random.Random(0)

        def initialize(preview, action_id):
            return prepare_server_initialization(
                character,
                {-7: creature},
                preview,
                3,
                deck,
                action_id=action_id,
                rng=rng,
                fight_start=True,
            )

        def stats(actor):
            if actor.controlled:
                return actual_actor_stats(
                    character,
                    actor,
                    fight.id,
                    wp_current=actor.effect_stats[4],
                    wp_maximum=audit.BREEDS[9]["resources"]["WP"],
                )
            return actual_monster_actor_stats(
                creature,
                actor,
                fight.id,
                wp_current=creature["wp"],
                wp_maximum=creature["wp"],
            )

        fight, runtime, ready_packets = prepare_ready(
            fight,
            3,
            True,
            initialize=initialize,
            stats_serializer=stats,
            effects_serializer=actor_effects,
            turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                character, {-7: creature}, preview, deck, rng=rng, **boundary
            ),
            turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                character,
                {-7: creature},
                preview,
                deck,
                rng=rng,
                native_events=True,
                area_callbacks=True,
                **boundary
            ),
        )
        row = dict(
            prefix=list(prefix),
            caster_level=20,
            caster_los_height=fight.actors[7].native_los_height,
            target_los_height=fight.actors[-7].native_los_height,
            actual_target_cast_rays=cast_rays(
                1134,
                source,
                target,
                source_height=fight.actors[7].native_los_height,
                target_height=fight.actors[-7].native_los_height,
            ),
            target_reference=creature.get("ref", creature.get("reference")),
            target_level=133,
            target_initial_hp=fight.actors[-7].hp,
            ready_packet_count=len(ready_packets),
            initialization=repr(fight.native_class_initializations),
            steps=[],
        )
        rows.append(row)

        def advance_owner(force=False):
            steps = []
            for index in range(len(runtime.fight.order) + 1):
                current = runtime.fight.current
                if current.id == character["id"] and (not force or index > 0):
                    break
                packets = (
                    runtime.end_turn(current.owner_id, current.id, current.turn_count)
                    if current.controlled
                    else runtime.end_server_turn(current.id, runtime.fight.turn_id)
                )
                pending = runtime.awaiting_ack
                if pending is not None:
                    packets += runtime.acknowledge_turn(struct.pack(">i", pending))
                steps.append(
                    dict(actor_id=current.id, ack=pending, packets=len(packets))
                )
            return steps

        row["initial_turn_boundaries"] = advance_owner()
        # Alternate original arrows; use normal caster costs and limits. Every
        # committed result is the source of the next request in this sequence.
        sequence = list(prefix) + [4816, 4820, 4810] * 4
        for reference in sequence:
            fight = runtime.fight
            if fight.phase != "active" or fight.actors[-7].hp <= 0:
                row["stop_reason"] = "Actual target died or combat ended"
                break
            factory, adapter = server_runtime(
                character, {-7: creature}, deck, action_id=2, critical=False, rng=rng
            )
            grant = granted_spells(fight, character["id"]).get(reference)
            uid = grant["uid"] if grant else (character["id"] << 32) | reference
            cell = source if reference == 7752 else precision_cell
            records, events, activations = [], [], []
            step = dict(
                spell=reference, target=cell, before=actor_summary(fight.actors[7])
            )
            row["steps"].append(step)

            def los(origin, destination, preview):
                return authoritative_visible(
                    preview.map_id,
                    origin,
                    destination,
                    preview,
                    blocking_footprints={
                        a.id: {a.position[:2]}
                        for a in preview.actors.values()
                        if a.hp > 0
                    },
                )

            try:
                with native_event_trace(events, activations):
                    transaction = prepare_spell_transaction(
                        struct.pack(">qqiih", character["id"], uid, *cell),
                        character,
                        fight,
                        3,
                        deck,
                        wp_current=fight.actors[7].effect_stats[4],
                        action_id=2,
                        line_of_sight=los,
                        runtime_factory=audit.observed(factory, records),
                        conditional_context=lambda request, preview: adapter.cast_condition(
                            preview, request
                        ),
                        critical=False,
                    )
                runtime.fight = transaction.fight
                step.update(
                    status="committed",
                    costs=transaction.plan["costs"],
                    after=actor_summary(transaction.fight.actors[7]),
                    target_hp=transaction.fight.actors[-7].hp,
                )
            except Exception as error:
                step.update(
                    status="rejected",
                    reason=str(error),
                    error_type=type(error).__name__,
                )
            step.update(trace=records, events=events, activations=activations)
            states = runtime.fight.actors[7].state_ledger.entries
            if any(state.reference == 7792 and state.level >= 30 for state in states):
                row["precision30_reached"] = True
                row["verified_actions_to_threshold"] = [
                    s["spell"] for s in row["steps"] if s["status"] == "committed"
                ]
                row["state_at_threshold"] = actor_summary(runtime.fight.actors[7])
                row["wall_followup_branches"] = []
                threshold_source = runtime.fight
                threshold_rng = rng.getstate()
                # Each branch starts from the same actual committed threshold.
                # B does not spend AP on the earlier wall cast from branch A.
                for name, actions in (
                    ("conditional_wall", ((7752, source), (4813, wall_cell))),
                    (
                        "restored_los_control",
                        ((7752, source), (7752, source), (4813, wall_cell)),
                    ),
                ):
                    actual = copy.deepcopy(threshold_source)
                    branch_rng = random.Random()
                    branch_rng.setstate(threshold_rng)
                    branch = dict(
                        name=name,
                        steps=[],
                        source_ap=actual.actors[7].ap,
                        source_actor=actor_summary(actual.actors[7]),
                        scope=(
                            "Independent actual threshold; native occupied blocker target"
                            if blocking_fixture
                            else "Independent actual threshold; original non-blocking empty cell control"
                        ),
                    )
                    row["wall_followup_branches"].append(branch)
                    for following, destination in actions:
                        entry = dict(
                            spell=following,
                            target=destination,
                            target_hp_before=actual.actors[-7].hp,
                            before=actor_summary(actual.actors[7]),
                            ap_before=actual.actors[7].ap,
                        )
                        branch["steps"].append(entry)
                        next_factory, next_adapter = server_runtime(
                            character,
                            {-7: creature},
                            deck,
                            action_id=3,
                            critical=False,
                            rng=branch_rng,
                        )
                        owned = granted_spells(actual, 7).get(following)
                        casting_uid = owned["uid"] if owned else (7 << 32) | following
                        try:
                            result = prepare_spell_transaction(
                                struct.pack(">qqiih", 7, casting_uid, *destination),
                                character,
                                actual,
                                3,
                                deck,
                                wp_current=actual.actors[7].effect_stats[4],
                                action_id=3,
                                line_of_sight=los,
                                runtime_factory=next_factory,
                                conditional_context=lambda request, preview: next_adapter.cast_condition(
                                    preview, request
                                ),
                                critical=False,
                            )
                            actual = result.fight
                            entry.update(
                                status="committed",
                                costs=result.plan["costs"],
                                after=actor_summary(result.fight.actors[7]),
                                ap_after=result.fight.actors[7].ap,
                                packet_count=len(result.packets),
                                native_casting_selection=result.plan.get(
                                    "native_casting_selection"
                                ),
                                target_hp_after=result.fight.actors[-7].hp,
                                target_actor_position=list(
                                    result.fight.actors[-7].position
                                ),
                            )
                        except Exception as error:
                            entry.update(
                                status="rejected",
                                reason=str(error),
                                native_casting_result=getattr(
                                    error, "native_casting_result", None
                                ),
                            )
                break
            # Refresh only through actual production turn end/ACK/start.
            # Failed requests remain recorded; their source has not been mutated.
            step["turn_boundaries_after"] = advance_owner(force=True)
            step["after_turn_cycle"] = actor_summary(runtime.fight.actors[7])
        row.setdefault("precision30_reached", False)
        print(
            json.dumps(
                dict(
                    prefix=prefix,
                    precision30_reached=row["precision30_reached"],
                    stop_reason=row.get("stop_reason"),
                )
            ),
            flush=True,
        )
    report = dict(
        source=source,
        target=target,
        precision_target_cell=precision_cell,
        wall_cell=wall_cell,
        blocking_fixture=blocking_fixture,
        map_id=1134,
        deck=[4810, 4813, 4816, 4820],
        scope="actual owned casts and committed state lifecycle; no state injection",
        rows=rows,
        source_hashes=hashes,
        sources_stable=hashes == audit.init.source_hashes(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=repr) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--blocking-fixture", action="store_true")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.output, args.blocking_fixture)
