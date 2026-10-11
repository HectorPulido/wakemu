#!/usr/bin/env python3
"""Actual Ready, legal6967 empty-cell glyph creation, movement and normal expiry."""
import argparse
from collections import deque
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import struct
from unittest.mock import patch
import audit_ready_start as ready_audit
from class_spell_eligible_targets import eligible_cast_targets
from wakfu_server.combat_server_spell import prepare_server_spell, server_runtime
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_effect_area_geometry import registered_area_cells
from wakfu_server.combat_effect_area import native_effect_areas
from wakfu_server.combat_area_transaction import prepare_area_movement
from wakfu_server.combat_movement_runtime import apply_client
from wakfu_server.combat_diagnostics import combat_diagnostic_scope
from wakfu_server.fight_checkpoint_store import snapshot


def path_to(fight, actor, destinations):
    occupied = {
        value.position
        for value in fight.actors.values()
        if value.id != actor.id and value.hp > 0
    }
    edges = {}
    for source, target in fight.edges or ():
        edges.setdefault(tuple(source), []).append(tuple(target))
    queue = deque([(tuple(actor.position), [])])
    seen = set()
    while queue:
        current, path = queue.popleft()
        if current in seen:
            continue
        seen.add(current)
        if path and current in destinations:
            from wakfu_server.combat_tackle_movement import movement_tackle_cost
            from wakfu_server.combat_rail_movement import movement_cost

            tackle_ap, tackle_mp = movement_tackle_cost(fight, actor, path)
            base_mp, _ = movement_cost(fight, actor, path)
            if tackle_ap <= actor.ap and base_mp + tackle_mp <= actor.mp:
                return path
        if len(path) >= actor.mp:
            continue
        for cell in edges.get(current, ()):
            if cell in fight.walkable and cell not in occupied and cell not in seen:
                queue.append((cell, path + [cell]))
    raise ValueError("No legal owned movement path within current MP")


def run(output, *, level=200):
    tool_before = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    details = {
        "status": "pending",
        "full_client_verified": False,
        "turn_start_policy": "Server glyph10000 mapping, not recovered original server producer",
    }
    original_fixture = ready_audit.fixture_module.fixture

    def fixture(*args, **kwargs):
        kwargs["monster_reference"], kwargs["monster_level"] = 5574, 133
        return original_fixture(*args, **kwargs)

    def on_runtime(runtime, character, monster, deck, packets, stats):
        source = runtime.fight
        if source.current.id != character["id"]:
            raise ValueError("Owned Feca does not hold actual Ready turn")
        caster = source.actors[character["id"]]
        before = snapshot(source)
        rng = random.Random(7)

        def los(a, b, preview):
            return authoritative_visible(
                preview.map_id,
                a,
                b,
                preview,
                blocking_footprints={
                    actor.id: {actor.position[:2]}
                    for actor in preview.actors.values()
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
        uid = (caster.id << 32) | 6967
        search = eligible_cast_targets(
            source,
            character,
            deck,
            uid,
            adapter=adapter,
            line_of_sight=los,
            maximum_eligible=16,
            limit=256,
        )
        enemy = source.actors[monster["id"]]
        definition = native_effect_areas()["1474"]
        failures = []
        for candidate in search["eligible"]:
            center = tuple(candidate["target"])
            if any(actor.position == center for actor in source.actors.values()):
                continue
            cells = registered_area_cells(definition, center, 0)
            if enemy.position[:2] not in cells or caster.position[:2] in cells:
                continue
            trace = []
            try:
                with combat_diagnostic_scope(
                    lambda **event: trace.append(event), limit=8192
                ):
                    transaction = prepare_server_spell(
                        struct.pack(">qqiih", caster.id, uid, *center),
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
            except Exception as error:
                assert snapshot(source) == before
                failures.append(
                    dict(center=center, reason=str(error), trace_tail=trace[-12:])
                )
                continue
            damage_areas = [
                row
                for row in transaction.fight.native_effect_areas.values()
                if row["reference"] == 1474
            ]
            marker_areas = [
                row
                for row in transaction.fight.native_effect_areas.values()
                if row["reference"] == 1477
            ]
            if len(damage_areas) != 1 or len(marker_areas) != 1:
                raise AssertionError(
                    "Original6967 empty branch did not create paired1474/1477 glyphs"
                )
            area = damage_areas[0]
            assert (
                set(map(tuple, area["native_cells_xy"])) == set(cells)
                and len(cells) == 5
            )
            assert area["owner_id"] == caster.id
            assert (
                transaction.fight.actors[enemy.id].hp == enemy.hp
            ), "Creation activated glyph unexpectedly"
            assert snapshot(source) == before
            resources = lambda actor: dict(
                ap=actor.ap, mp=actor.mp, wp=actor.effect_stats[4]
            )
            details.update(
                status="creation_completed",
                center=center,
                caster_origin=tuple(caster.position),
                footprint=sorted(cells),
                resources_before=resources(caster),
                resources_after=resources(transaction.fight.actors[caster.id]),
                ordinary_costs=transaction.plan["costs"],
                created_areas=[
                    dict(
                        uid=row["uid"],
                        reference=row["reference"],
                        owner_id=row["owner_id"],
                    )
                    for row in damage_areas + marker_areas
                ],
                actual_timer=transaction.fight.native_owned_area_effects[
                    area["effect_uid"]
                ].get("timer"),
                enemy=dict(
                    reference=monster["ref"],
                    level=133,
                    position=tuple(enemy.position),
                    hp_before=enemy.hp,
                ),
                trace=trace,
                eligible_search=search,
                attempted_rejections=failures,
            )
            commit_spell_transaction(runtime, transaction, stats_serializer=stats)

            def movement(path):
                def provider(fight, **kwargs):
                    return prepare_area_movement(
                        character,
                        {monster["id"]: monster},
                        fight,
                        deck,
                        rng=rng,
                        **kwargs
                    )

                body = struct.pack(">q", caster.id) + b"".join(
                    struct.pack(">iih", *cell) for cell in path
                )
                return apply_client(
                    runtime,
                    character["account_id"],
                    body,
                    lambda actor: stats(actor, runtime.fight),
                    area_provider=provider,
                )

            live = runtime.fight
            inside = {cell for cell in live.walkable if cell[:2] in cells}
            hp_before = {key: actor.hp for key, actor in live.actors.items()}
            try:
                first = path_to(live, live.actors[caster.id], inside)
                movement(first)
                outside = {
                    cell for cell in runtime.fight.walkable if cell[:2] not in cells
                }
                second = path_to(
                    runtime.fight, runtime.fight.actors[caster.id], outside
                )
                movement(second)
                details["movement"] = dict(enter=first, exit=second, no_activation=True)
            except ValueError as error:
                details["movement"] = dict(status="not_qualified", reason=str(error))
            assert {
                key: actor.hp for key, actor in runtime.fight.actors.items()
            } == hp_before, "Movement activated glyph"
            turns = []
            enemy_hp_before = runtime.fight.actors[enemy.id].hp
            for _ in range(4):
                current = runtime.fight.current
                boundary = (
                    runtime.end_turn(current.owner_id, current.id, current.turn_count)
                    if current.controlled
                    else runtime.end_server_turn(current.id, runtime.fight.turn_id)
                )
                ack = runtime.awaiting_ack
                if ack is not None:
                    boundary += runtime.acknowledge_turn(struct.pack(">i", ack))
                turns.append(
                    dict(
                        ended_actor=current.id,
                        current_actor=None
                        if runtime.fight.current is None
                        else runtime.fight.current.id,
                        enemy_hp=runtime.fight.actors[enemy.id].hp,
                        areas=[
                            row["reference"]
                            for row in runtime.fight.native_effect_areas.values()
                        ],
                        packet_count=len(boundary),
                    )
                )
                if not any(
                    row["reference"] == 1474
                    for row in runtime.fight.native_effect_areas.values()
                ):
                    break
                if runtime.fight.phase != "active":
                    raise ValueError("Fight ended before normal glyph expiry")
            details["turns"] = turns
            assert (
                runtime.fight.actors[enemy.id].hp < enemy_hp_before
            ), "Eligible enemy turn-start did not activate actual1474"
            assert not any(
                row["reference"] in (1474, 1477)
                for row in runtime.fight.native_effect_areas.values()
            ), "Paired glyphs did not expire normally"
            assert runtime.fight.current.id == caster.id
            after_hp = {key: actor.hp for key, actor in runtime.fight.actors.items()}
            try:
                old_entry = path_to(
                    runtime.fight, runtime.fight.actors[caster.id], inside
                )
                movement(old_entry)
            except ValueError as error:
                old_entry = dict(status="not_qualified", reason=str(error))
            assert {
                key: actor.hp for key, actor in runtime.fight.actors.items()
            } == after_hp
            details.update(
                status="lifecycle_completed",
                expired=True,
                post_expiry_movement=old_entry,
                source_preserved=True,
                checkpoint_plain=True,
            )
            json.dumps(snapshot(runtime.fight), allow_nan=False)
            return details
        details.update(
            status="creation_rejected",
            eligible_search=search,
            attempted_rejections=failures,
        )
        raise ValueError(
            "No actual legal empty-cell6967 glyph candidate covering common enemy"
        )

    with patch.object(ready_audit.fixture_module, "fixture", fixture):
        report = ready_audit.run(
            output,
            cases_override=[(1, level, None)],
            on_runtime=on_runtime,
            turn_cycle=True,
            turn_steps=1,
        )
    report["feca_glyph_manual"] = details
    report["audit_tool_sha256"] = tool_before
    report["audit_tool_source_stable"] = (
        tool_before == hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    )
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
    args = parser.parse_args()
    report = run(args.output, level=args.level)
    print(
        json.dumps(
            {
                "status": report["feca_glyph_manual"]["status"],
                "rows": [(row["status"], row.get("reason")) for row in report["rows"]],
                "source_stable": report["source_stable"],
            }
        )
    )
