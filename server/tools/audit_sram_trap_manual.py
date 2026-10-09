#!/usr/bin/env python3
"""Offline actual Sram Ready grant, legal trap cast and owned movement lifecycle."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import struct
from unittest.mock import patch
from sram_trap_audit_config import (
    CANDIDATE_LIMIT,
    MAXIMUM_ELIGIBLE,
    validate_configuration,
)

import audit_ready_start as ready_audit
from audit_feca_glyph_manual import path_to
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_spell_grant_book import grant_record
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_effect_area_geometry import registered_area_cells
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_movement_runtime import (
    apply_client,
    _with_areas,
    direction_after_path,
)
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot


def run(output, *, level=200, spell=5182, mover="owner"):
    validate_configuration(level=level, spell=spell, mover=mover)
    tool_hash = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    dependency_paths = [
        Path(__file__).with_name(name)
        for name in ("sram_trap_audit_config.py", "audit_feca_glyph_manual.py")
    ]
    dependency_hashes = {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in dependency_paths
    }
    details = dict(
        status="pending",
        full_client_verified=False,
        spell=spell,
        mover=mover,
        exhaustion_policy="wakemu.successful-activation.Qq.baD-v1",
    )
    original_fixture = ready_audit.fixture_module.fixture

    def fixture(*args, **kwargs):
        kwargs["monster_reference"], kwargs["monster_level"] = 5574, 133
        return original_fixture(*args, **kwargs)

    def on_runtime(runtime, character, monster, deck, packets, stats):
        source = runtime.fight
        caster = source.actors[character["id"]]
        mover_id = caster.id if mover == "owner" else monster["id"]
        record = grant_record(source, caster.id, spell)
        details["grant"] = record
        if record is None:
            raise ValueError("Actual Ready did not grant the selected trap action")
        if source.current is not caster:
            raise ValueError("Actual Sram does not hold the Ready turn")
        before = snapshot(source)
        rng = random.Random(7)

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

        _, adapter = server_runtime(
            character,
            {monster["id"]: monster},
            deck,
            action_id=runtime.action_id + 1,
            critical=False,
            rng=rng,
        )
        search = eligible_cast_targets(
            source,
            character,
            deck,
            record["uid"],
            adapter=adapter,
            line_of_sight=los,
            maximum_eligible=MAXIMUM_ELIGIBLE,
            limit=CANDIDATE_LIMIT,
        )
        details["eligible_search"] = search
        failures = []
        for candidate in search["eligible"]:
            center = tuple(candidate["target"])
            if any(actor.position == center for actor in source.actors.values()):
                continue
            trace = []
            try:
                with combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=8192
                ):
                    transaction = prepare_server_spell(
                        struct.pack(">qqiih", caster.id, record["uid"], *center),
                        character,
                        {monster["id"]: monster},
                        source,
                        character["account_id"],
                        deck,
                        action_id=runtime.action_id + 1,
                        line_of_sight=los,
                        critical=False,
                        rng=rng,
                    )
                traps = [
                    row
                    for row in transaction.fight.native_effect_areas.values()
                    if row.get("native_area_contract") == "fbc"
                ]
                if len(traps) != 1:
                    raise ValueError(
                        "Selected normal grant did not create exactly one actual trap"
                    )
                row = traps[0]
                definition = native_effect_areas()[str(row["reference"])]
                footprint = registered_area_cells(
                    definition, row["cell"], row["direction"]
                )
                if caster.position[:2] in footprint:
                    raise ValueError(
                        "Candidate already overlaps the owner before movement"
                    )
                if source.actors[mover_id].position[:2] in footprint:
                    raise ValueError(
                        "Candidate already overlaps the mover before movement"
                    )
                destinations = {
                    cell for cell in transaction.fight.walkable if cell[:2] in footprint
                }
                path = path_to(
                    transaction.fight, transaction.fight.actors[mover_id], destinations
                )
            except Exception as error:
                assert snapshot(source) == before
                failures.append(
                    dict(
                        center=center,
                        error=type(error).__name__,
                        reason=str(error),
                        trace_tail=trace[-16:],
                    )
                )
                continue
            assert snapshot(source) == before
            details.update(
                status="creation_completed",
                center=center,
                footprint=sorted(footprint),
                caster_origin=tuple(caster.position),
                trap_reference=row["reference"],
                trap_uid=row["uid"],
                charges_before=row["remaining_activations"],
                trap_characteristics=dict(row["native_trap_characteristics"]),
                costs=transaction.plan["costs"],
                resources_before=dict(ap=caster.ap, mp=caster.mp),
                resources_after=dict(
                    ap=transaction.fight.actors[caster.id].ap,
                    mp=transaction.fight.actors[caster.id].mp,
                ),
                attempted_rejections=failures,
                creation_trace=trace,
                planned_path=path,
            )
            commit_spell_transaction(runtime, transaction, stats_serializer=stats)
            if mover == "enemy":
                for _ in range(len(runtime.fight.order)):
                    if runtime.fight.current.id == mover_id:
                        break
                    current = runtime.fight.current
                    if current.controlled:
                        runtime.end_turn(
                            current.owner_id, current.id, current.turn_count
                        )
                    else:
                        runtime.end_server_turn(current.id, runtime.fight.turn_id)
                    if runtime.awaiting_ack is not None:
                        runtime.acknowledge_turn(
                            struct.pack(">i", runtime.awaiting_ack)
                        )
                if runtime.fight.current.id != mover_id:
                    raise ValueError("Actual enemy turn did not become current")
                path = path_to(
                    runtime.fight, runtime.fight.actors[mover_id], destinations
                )
            details["mover_origin"] = tuple(runtime.fight.actors[mover_id].position)
            details["planned_path"] = path
            movement_trace = []

            def provider(fight, **kwargs):
                return prepare_area_movement(
                    character, {monster["id"]: monster}, fight, deck, rng=rng, **kwargs
                )

            body = struct.pack(">q", mover_id) + b"".join(
                struct.pack(">iih", *cell) for cell in path
            )
            movement_before = snapshot(runtime.fight)
            try:
                with combat_diagnostic_scope(
                    lambda **event: movement_trace.append(event), limit=8192
                ):
                    if mover == "owner":
                        movement_packets, event = apply_client(
                            runtime,
                            character["account_id"],
                            body,
                            lambda actor: stats(actor, runtime.fight),
                            area_provider=provider,
                        )
                    else:

                        def server_path(candidate_runtime):
                            from wakfu_server.combat_carrying import (
                                set_registered_direction,
                            )

                            actor = candidate_runtime.fight.current
                            if actor.id != mover_id or actor.controlled:
                                raise ValueError("Actual unowned NPC turn required")
                            facing = direction_after_path(
                                actor.position, path, actor.direction
                            )
                            event = candidate_runtime.fight.server_move(actor.id, path)
                            set_registered_direction(
                                candidate_runtime.fight, actor, facing
                            )
                            candidate_runtime.action_id += 1
                            return [], event

                        # Same atomic movement/area wrapper used by apply_ai,
                        # with a typed legal FSM path and no planner invocation.
                        movement_packets, event = _with_areas(
                            runtime, provider, server_path
                        )
            except Exception as error:
                assert snapshot(runtime.fight) == movement_before
                details.update(
                    status="activation_rejected",
                    reason=str(error),
                    movement_source_preserved=True,
                    movement_trace=movement_trace,
                )
                raise
            live = runtime.fight
            details.update(
                movement_trace=movement_trace,
                movement_event=event,
                final_position=tuple(live.actors[mover_id].position),
                packet_count=len(movement_packets),
                active_area_uids=sorted(live.native_effect_areas),
                retired_manager_uids=sorted(
                    getattr(live, "native_retired_area_managers", {})
                ),
            )
            assert (
                row["uid"] not in live.native_effect_areas
            ), "Finite trap survived successful activation"
            details.update(status="lifecycle_completed", exhausted_removed=True)
            json.dumps(snapshot(live), allow_nan=False)
            return details
        details.update(status="creation_rejected", attempted_rejections=failures)
        raise ValueError("No actual legal trap creation and owner movement context")

    with patch.object(ready_audit.fixture_module, "fixture", fixture):
        report = ready_audit.run(
            output,
            cases_override=[(4, level, None)],
            on_runtime=on_runtime,
            turn_cycle=True,
            turn_steps=1,
        )
    report["sram_trap_manual"] = details
    report["audit_tool_sha256"] = tool_hash
    report["audit_tool_dependency_sha256"] = dependency_hashes
    report["audit_tool_source_stable"] = tool_hash == hashlib.sha256(
        Path(__file__).read_bytes()
    ).hexdigest() and dependency_hashes == {
        path.name: hashlib.sha256(path.read_bytes()).hexdigest()
        for path in dependency_paths
    }
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
    parser.add_argument("--level", type=int, default=200)
    parser.add_argument("--spell", type=int, choices=(5182, 5183), default=5182)
    parser.add_argument("--mover", choices=("owner", "enemy"), default="owner")
    args = parser.parse_args()
    result = run(args.output, level=args.level, spell=args.spell, mover=args.mover)
    print(
        json.dumps(
            dict(
                status=result["sram_trap_manual"]["status"],
                rows=[(row["status"], row.get("reason")) for row in result["rows"]],
                source_stable=result["source_stable"],
            )
        )
    )
