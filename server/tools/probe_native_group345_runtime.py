#!/usr/bin/env python3
"""Isolate installed345 nodes on real initialized actors; no full-cast claim."""
import sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "tools"))
import audit_active_spells as audit
from wakfu_server import combat_multiple_target_group as group

observations = []
original = group.select_multiple_targets


def select(values, candidates, **kwargs):
    candidates = tuple(candidates)
    result = original(values, candidates, **kwargs)
    observations.append(
        {
            "reference": None if not candidates else candidates[0].reference,
            "level": None if not candidates else candidates[0].level,
            "parameters": values["parameters"],
            "candidates": [x.target_id for x in candidates],
            "selected": [
                {"id": x.target_id, "cell": list(kwargs["position"](x.target_id))}
                for x in result
            ],
        }
    )
    return result


group.select_multiple_targets = select

base_fixture = audit.fixture
base_runtime = audit.server_runtime
extra_monsters = {}


def fixture(breed, level, enemy_cell, terrain, origin, **kwargs):
    character, creature, unused = base_fixture(
        breed, level, enemy_cell, terrain, origin, ready=False, **kwargs
    )
    cells = [
        c
        for c in terrain["cells"]
        if c not in (enemy_cell, origin)
        and 1 <= abs(c[0] - enemy_cell[0]) + abs(c[1] - enemy_cell[1]) <= 3
        and abs(c[0] - origin[0]) + abs(c[1] - origin[1]) == 1
        and c[2] == origin[2]
    ]
    if not cells:
        raise ValueError("No native secondary cell in group range")
    cell = sorted(cells)[0]
    secondary = audit.owned_instance(
        kwargs["monster_reference"],
        kwargs["monster_level"],
        -8,
        map_id=1134,
        x=cell[0],
        y=cell[1],
        z=cell[2],
    )
    placement = {0: {origin}, 1: {enemy_cell, cell}}
    arena = audit.encode_arena(1134, 0, terrain["cells"], placement)
    arena.update(
        validated_cells=terrain["cells"],
        valid_edges=terrain["edges"],
        placement_cells=placement,
    )
    resource = audit.BREEDS[breed]["resources"]
    fight, _ = audit.create_placement(
        character,
        [creature, secondary],
        arena,
        fight_id=10000 + breed * 100 + level,
        player_ap=resource["AP"],
        player_mp=resource["MP"],
        player_wp=resource["WP"],
        player_initiative=0,
        terrain_effect_id=46,
        terrain_instance_id=-300,
    )
    audit.initialize_fight_snapshots(
        fight,
        characters={7: character},
        monsters={-7: creature, -8: secondary},
        wp_resources={
            7: (resource["WP"], resource["WP"]),
            -7: (creature["wp"], creature["wp"]),
            -8: (secondary["wp"], secondary["wp"]),
        },
        running_effects={7: (), -7: (), -8: ()},
        initial_effect_uid=200,
    )
    fight.actors[7].direction = 0
    for uid in (-7, -8):
        fight.actors[uid].direction = 3
    fight.map_id = 1134
    fight.instance_id = 0
    fight.ready(3)
    extra_monsters.clear()
    extra_monsters[-8] = secondary
    return character, creature, fight


def runtime(character, monsters, deck, **kwargs):
    return base_runtime(
        character, dict(monsters, **{}) | extra_monsters, deck, **kwargs
    )


audit.fixture = fixture
audit.server_runtime = runtime


from copy import deepcopy
from random import Random
from wakfu_server.combat_cast import prepare_spell_cast
from wakfu_server.combat_server_spell import prepare_server_initialization
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.combat_arena_selection import bounded_arena
import struct

origin = (-8, -7, -1)
geometry = map_geometry(1134)
terrain = bounded_arena(geometry, origin, [(-7, -7, -1)], radius=12)
rows = []
source_before = audit.init.source_hashes()
for level in (13, 200):
    for critical in (False, True):
        character, creature, base = fixture(
            13,
            level,
            (-9, -7, -1),
            terrain,
            origin,
            monster_reference=1367,
            monster_level=115,
        )
        monsters = {-7: creature} | extra_monsters
        deck = encode_deck([6475])
        rng = Random(7)
        source, opening = prepare_server_initialization(
            character, monsters, base, 3, deck, action_id=1, rng=rng, fight_start=True
        )
        while source.current is not None and source.current.id != 7:
            source.end_server_turn(source.current.id, source.turn_id)
        before = snapshot(source)
        preview = deepcopy(source)
        shared, adapter = base_runtime(
            character, monsters, deck, action_id=2, critical=critical, rng=rng
        )
        body = struct.pack(">qqiih", 7, (7 << 32) | 6475, *preview.actors[-7].position)
        plan = prepare_spell_cast(
            body,
            character,
            preview,
            3,
            deck,
            wp=preview.actors[7].effect_stats[4],
            line_of_sight=lambda a, b, p: audit.authoritative_visible(1134, a, b, p),
            conditional_context=lambda request, preview: adapter.cast_condition(
                preview, request
            ),
        )
        dispatcher, packets = shared(preview, plan)
        ref = 370940 if critical else 370906
        count = len(observations)
        row = {
            "scope": "isolated installed 345 leaf, validated source spell plan; not full cast/no costs spent",
            "level": level,
            "critical": critical,
            "reference": ref,
            "native_monsters": [
                {
                    "id": m["id"],
                    "reference": m["ref"],
                    "level": m["level"],
                    "hp": m["hp"],
                    "cell": [m["x"], m["y"], m["z"]],
                }
                for m in monsters.values()
            ],
        }
        try:
            start = len(preview.events)
            with preview.effect_resolution():
                row["applied"] = dispatcher.execute(
                    EffectInvocation(ref, level, 7, None, preview.actors[-7].position)
                )
            row["events"] = preview.events[start:]
            row["packets"] = [op for op, _ in packets]
            row["selected"] = observations[count:]
            row["status"] = "applied" if row["applied"] else "no_effect"
        except Exception as e:
            row["status"] = "rejected"
            row["error"] = str(e)
            row["selected"] = observations[count:]
        row["rollback_preserved"] = snapshot(source) == before
        rows.append(row)
report = {
    "source_before": source_before,
    "source_after": audit.init.source_hashes(),
    "rows": rows,
    "scope": "native leaf isolation only; no GUI/full spell claim",
}
report["sources_stable"] = report["source_before"] == report["source_after"]
(ROOT / "docs/reports/combat-inventory/group345-native-leaf-runtime.json").write_text(
    json.dumps(report, ensure_ascii=False, indent=2) + "\n"
)
print(json.dumps(rows, ensure_ascii=False))

if not report["sources_stable"] or not all(
    row.get("status") == "applied" and row["rollback_preserved"] for row in rows
):
    raise SystemExit(1)
