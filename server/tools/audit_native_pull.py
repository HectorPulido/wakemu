#!/usr/bin/env python3
"""Real common spell preparation on exported terrain; inspect actual pull path."""
import argparse
from collections import Counter
import datetime
import json
from pathlib import Path
from random import Random
import struct
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "server/tools")]
import audit_active_spells as audit
from audit_class_initialization import source_hashes
from wakfu_server.spell_audit import catalog
from wakfu_server.spells import SPELLS, encode_deck
from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_los import static_visible, authoritative_visible
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.fight_checkpoint_store import snapshot


def distance(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def run(spell_id, levels, output, *, origin=(-8, -7, -1), targets=None):
    before_hashes = source_hashes()
    exported = catalog()["spells"][str(spell_id)]
    breed = SPELLS[spell_id]["breed"]
    geometry = map_geometry(1134)
    origin = tuple(origin)
    terrain = bounded_arena(
        geometry, origin, targets or [(origin[0] + 1, origin[1], origin[2])], radius=12
    )
    names = json.loads((ROOT / "server/protocol/spell-names.json").read_text())[
        "spells"
    ]
    name = next(row["name"] for row in names if row["id"] == spell_id)
    rows = []
    for level in levels:
        minimum, maximum_range, _ = exported["levels"][level - 1]
        candidates = {}
        for cell in sorted(targets or terrain["cells"]):
            dx, dy = cell[0] - origin[0], cell[1] - origin[1]
            d = distance(origin, cell)
            if (
                (targets is None and cell[2] != origin[2])
                or not minimum <= d <= maximum_range
                or d == 0
                or (dx and dy)
            ):
                continue
            step = (0 if dx == 0 else dx // abs(dx), 0 if dy == 0 else dy // abs(dy))
            path = [
                (origin[0] + i * step[0], origin[1] + i * step[1], origin[2])
                for i in range(1, d + 1)
            ]
            if targets is None and any(p not in terrain["cells"] for p in path):
                continue
            try:
                if (
                    targets is None
                    and exported["line_of_sight"]
                    and not static_visible(1134, origin, cell)
                ):
                    continue
            except ValueError:
                continue
            candidates.setdefault(d, cell)
        # Adjacent is a control; several distances expose movement independently
        # of optional armor changes and root success booleans.
        chosen = (
            sorted(
                {min(candidates), max(candidates), *([2, 3, 4] if candidates else [])}
                & set(candidates)
            )
            if candidates
            else []
        )
        if not chosen:
            rows.append(
                dict(
                    level=level,
                    status="NO_LEGAL_TARGET",
                    range=[minimum, maximum_range],
                )
            )
            continue
        for d in chosen:
            cell = candidates[d]
            character, monster, base = audit.fixture(
                breed, level, cell, terrain, origin
            )
            deck = encode_deck([spell_id])
            before_base = snapshot(base)
            row = dict(
                spell_id=spell_id,
                name=name,
                level=level,
                initial_distance=d,
                caster_position=list(origin),
                target_before=list(cell),
                range=[minimum, maximum_range],
            )
            source = None
            try:
                source, init_packets = prepare_server_initialization(
                    character,
                    {-7: monster},
                    base,
                    3,
                    deck,
                    action_id=1,
                    rng=Random(0),
                    fight_start=True,
                )
                if snapshot(base) != before_base:
                    raise AssertionError("Initialization mutated source")
                while source.current.id != 7:
                    source.end_server_turn(source.current.id, source.turn_id)
                prior = snapshot(source)

                def los(a, b, preview):
                    return authoritative_visible(
                        1134,
                        a,
                        b,
                        preview,
                        blocking_footprints={
                            actor.id: {actor.position[:2]}
                            for actor in preview.actors.values()
                            if actor.hp > 0
                        },
                    )

                result = prepare_server_spell(
                    struct.pack(">qqiih", 7, (7 << 32) | spell_id, *cell),
                    character,
                    {-7: monster},
                    source,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=los,
                    critical=False,
                    rng=Random(0),
                )
                target = result.fight.actors[-7]
                moved = target.position != source.actors[-7].position
                families = Counter(
                    struct.unpack_from(">i", packet, 13)[0]
                    for op, packet in result.packets
                    if op == 12613 and len(packet) >= 19
                )
                row.update(
                    status="MOVED" if moved else "NO_MOVEMENT",
                    target_after=list(target.position),
                    final_distance=distance(
                        result.fight.actors[7].position, target.position
                    ),
                    movement_observed=moved,
                    position_events=[
                        e for e in result.events if e["kind"] == "effect_displacement"
                    ],
                    actor_resources={
                        str(identity): dict(
                            hp_before=source.actors[identity].hp,
                            hp_after=actor.hp,
                            armor_before=source.actors[identity].effect_stats[97],
                            armor_after=actor.effect_stats[97],
                            armor_delta=actor.effect_stats[97]
                            - source.actors[identity].effect_stats[97],
                        )
                        for identity, actor in result.fight.actors.items()
                    },
                    events=list(result.events),
                    effect_packet_families=dict(families),
                    packet_opcodes=dict(Counter(op for op, _ in result.packets)),
                    outcomes=list(result.outcomes),
                    costs=result.plan["costs"],
                    rollback_preserved=snapshot(source) == prior,
                    init_rollback_preserved=snapshot(base) == before_base,
                )
            except Exception as error:
                row.update(
                    status="REJECT",
                    reason=str(error),
                    exception_type=type(error).__name__,
                    traceback=traceback.format_exc(),
                    init_rollback_preserved=snapshot(base) == before_base,
                    rollback_preserved=source is None or snapshot(source) == prior,
                )
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    after_hashes = source_hashes()
    report = dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        spell_id=spell_id,
        name=name,
        rows=rows,
        sources_stable=before_hashes == after_hashes,
        changed_sources=[
            p for p in before_hashes if before_hashes[p] != after_hashes[p]
        ],
        source_hashes=before_hashes,
        scope="Production prepare_server_initialization(fight_start=True) and prepare_server_spell; original roots/criteria, owned snapshots, actual map1134 terrain/QL/LOS, legal axial living NPC targets. No root/selector/value predicate override. Offline fixture, not a GUI acknowledgement test.",
    )
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            dict(
                counts=dict(Counter(row["status"] for row in rows)),
                sources_stable=report["sources_stable"],
            )
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("spell_id", type=int)
    parser.add_argument("levels", type=int, nargs="+")
    parser.add_argument("--output", required=True)
    parser.add_argument("--origin", type=int, nargs=3)
    parser.add_argument("--target", type=int, nargs=3)
    args = parser.parse_args()
    run(
        args.spell_id,
        args.levels,
        args.output,
        origin=tuple(args.origin or (-8, -7, -1)),
        targets=None if args.target is None else [tuple(args.target)],
    )
