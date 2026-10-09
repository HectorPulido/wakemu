#!/usr/bin/env python3
"""Actual Steamer Ready, owned Microbot casts and turn-driven retirement audit."""
import argparse
import copy
import json
import random
import struct
from pathlib import Path

import audit_active_spells as audit
from audit_class_summon_reactions import actor_summary
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
from wakfu_server.spells import encode_deck
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_area_transaction import prepare_area_movement


def snapshot(fight):
    return dict(
        actor=actor_summary(fight.actors[7]),
        areas=copy.deepcopy(getattr(fight, "native_effect_areas", {})),
        retired_areas=copy.deepcopy(getattr(fight, "native_retired_area_managers", {})),
        networks=copy.deepcopy(getattr(fight, "native_microbot_networks", {})),
        slots=copy.deepcopy(getattr(fight, "native_qi_slots", None)),
        touched=copy.deepcopy(getattr(fight, "native_qi_touched_cells", None)),
    )


def run(output):
    hashes = audit.init.source_hashes()
    source, enemy = (-8, -7, -1), (-14, -7, -1)
    terrain = audit.bounded_arena(audit.map_geometry(1134), source, [enemy], radius=12)
    # Maquinaria is an ordinary source-owned deck ability; Microbot is obtained
    # exclusively from the actual Ready grant. The tool never manufactures UID.
    deck = encode_deck([6919])
    character, creature, fight = audit.fixture(
        16,
        200,
        enemy,
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
                wp_maximum=audit.BREEDS[16]["resources"]["WP"],
            )
        return actual_monster_actor_stats(
            creature,
            actor,
            fight.id,
            wp_current=creature["wp"],
            wp_maximum=creature["wp"],
        )

    fight, runtime, packets = prepare_ready(
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
    report = dict(
        scope="actual owned transaction and production turn lifecycle",
        map_id=1134,
        breed=16,
        level=200,
        deck=[6919],
        ready_packets=len(packets),
        initialization=repr(fight.native_class_initializations),
        before=snapshot(fight),
        steps=[],
    )

    def turn_cycle(force=False):
        transitions = []
        for index in range(len(runtime.fight.order) + 1):
            current = runtime.fight.current
            if current.id == 7 and (not force or index):
                break
            emitted = (
                runtime.end_turn(current.owner_id, current.id, current.turn_count)
                if current.controlled
                else runtime.end_server_turn(current.id, runtime.fight.turn_id)
            )
            pending = runtime.awaiting_ack
            if pending is not None:
                emitted += runtime.acknowledge_turn(struct.pack(">i", pending))
            transitions.append(
                dict(actor=current.id, ack=pending, packets=len(emitted))
            )
        return transitions

    report["initial_turns"] = turn_cycle()

    def cast(cell):
        actual = runtime.fight
        step = dict(action="owned_microbot", cell=cell, before=snapshot(actual))
        report["steps"].append(step)
        grant = granted_spells(actual, 7).get(7008)
        if grant is None:
            step.update(status="blocked", reason="Actual Ready did not grant Microbot")
            return False
        factory, adapter = server_runtime(
            character, {-7: creature}, deck, action_id=2, critical=False, rng=rng
        )
        try:
            result = prepare_spell_transaction(
                struct.pack(">qqiih", 7, grant["uid"], *cell),
                character,
                actual,
                3,
                deck,
                wp_current=actual.actors[7].effect_stats[4],
                action_id=2,
                runtime_factory=factory,
                conditional_context=lambda request, preview: adapter.cast_condition(
                    preview, request
                ),
                line_of_sight=lambda origin, destination, preview: authoritative_visible(
                    preview.map_id,
                    origin,
                    destination,
                    preview,
                    blocking_footprints={
                        a.id: {a.position[:2]}
                        for a in preview.actors.values()
                        if a.hp > 0
                    },
                ),
                critical=False,
            )
            runtime.fight = result.fight
            step.update(
                status="committed",
                costs=result.plan["costs"],
                native_casting_selection=result.plan.get("native_casting_selection"),
                packets=len(result.packets),
                after=snapshot(result.fight),
            )
            return True
        except Exception as error:
            step.update(
                status="rejected",
                reason=str(error),
                native_casting_result=getattr(error, "native_casting_result", None),
            )
            return False

    # Actual source-map cells: retry is recorded and resources are refreshed
    # only by production end/ACK/start. No effect/area is directly installed.
    for cell in ((-7, -7, -1), (-5, -7, -1)):
        cast(cell)
        report["steps"].append(
            dict(
                action="turn_cycle",
                boundaries=turn_cycle(True),
                after=snapshot(runtime.fight),
            )
        )
    # Exercise actual owned movement. This records existing routing and exact
    # resource cost; network membership is not substituted for walkability.
    for path in (
        [(-7, -7, -1)],
        [(-6, -7, -1), (-5, -7, -1)],
        [(-6, -7, -1), (-7, -7, -1), (-8, -7, -1)],
    ):
        actual = runtime.fight
        step = dict(action="owned_move", path=path, before=snapshot(actual))
        report["steps"].append(step)
        try:
            body = struct.pack(">q", 7) + b"".join(
                struct.pack(">iih", *cell) for cell in path
            )
            emitted, event = apply_client(
                runtime,
                3,
                body,
                stats,
                area_provider=lambda preview, **boundary: prepare_area_movement(
                    character, {-7: creature}, preview, deck, rng=rng, **boundary
                ),
            )
            step.update(
                status="committed",
                event=event,
                packets=len(emitted),
                after=snapshot(runtime.fight),
            )
        except Exception as error:
            step.update(status="rejected", reason=str(error))
    # Timers are advanced by actual turn boundaries, allowing source duration
    # to decide retirement. A final cast tests reuse without direct removal.
    for _ in range(8):
        report["steps"].append(
            dict(
                action="retirement_turn_cycle",
                boundaries=turn_cycle(True),
                after=snapshot(runtime.fight),
            )
        )
    # First actual recast removes the existing bot; the second attempts a
    # fresh constructor on the now-vacant cell and must obtain a new UID.
    cast((-7, -7, -1))
    cast((-7, -7, -1))
    report.update(
        after=snapshot(runtime.fight),
        source_hashes=hashes,
        sources_stable=hashes == audit.init.source_hashes(),
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2, default=repr) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    run(parser.parse_args().output)
