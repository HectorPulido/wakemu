"""Offline injured Zurcarák common healing cast with native flag15/34."""
import json, random, struct, collections, hashlib
from pathlib import Path
import audit_active_spells as a
from wakfu_server.combat_server_spell import prepare_server_initialization


def run():
    def hashes():
        return {
            str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in Path("server/wakfu_server").rglob("*.py")
        }

    before_hash = hashes()
    geometry = a.map_geometry(1134)
    origin = (-8, -7, -1)
    terrain = a.bounded_arena(geometry, origin, [(-7, -7, -1)], radius=12)
    center = origin
    # Native walkable altitude, actual ring around caster; outside control actor.
    cells = [
        c
        for c in sorted(terrain["cells"])
        if max(abs(c[0] - center[0]), abs(c[1] - center[1])) == 1
        and c[:2] != origin[:2]
    ]
    cells = list({c[:2]: c for c in cells}.values())[:3]
    outside = next(
        c
        for c in sorted(terrain["cells"])
        if max(abs(c[0] - center[0]), abs(c[1] - center[1])) == 2
        and c[:2] != origin[:2]
    )
    rows = []
    for spell, breed, level in [(2067, 6, 11), (2067, 6, 200)]:
        character, _, _ = a.fixture(breed, level, cells[0], terrain, origin)
        members = [
            a.owned_instance(5525, 1, -7 - i, map_id=1134, x=c[0], y=c[1], z=c[2])
            for i, c in enumerate(cells + [outside])
        ]
        placements = {
            0: {origin},
            1: {tuple((m["x"], m["y"], m["z"])) for m in members},
        }
        arena = a.encode_arena(1134, 0, terrain["cells"], placements)
        arena.update(
            validated_cells=terrain["cells"],
            valid_edges=terrain["edges"],
            placement_cells=placements,
        )
        resource = a.BREEDS[breed]["resources"]
        base, _ = a.create_placement(
            character,
            members,
            arena,
            fight_id=17000 + level,
            player_ap=resource["AP"],
            player_mp=resource["MP"],
            player_wp=resource["WP"],
            player_initiative=0,
            terrain_effect_id=46,
            terrain_instance_id=-300,
        )
        monsters = {m["id"]: m for m in members}
        a.initialize_fight_snapshots(
            base,
            characters={7: character},
            monsters=monsters,
            wp_resources={
                7: (resource["WP"], resource["WP"]),
                **{m["id"]: (m["wp"], m["wp"]) for m in members},
            },
            running_effects={i: () for i in base.actors},
            initial_effect_uid=200,
        )
        base.actors[7].direction = 1
        for m in members:
            base.actors[m["id"]].direction = 3
        base.map_id = 1134
        base.instance_id = 0
        base.ready(3)
        deck = a.encode_deck([spell])
        rng = random.Random(0)
        source, _ = prepare_server_initialization(
            character, monsters, base, 3, deck, action_id=1, rng=rng, fight_start=True
        )
        while source.current.id != 7:
            source.end_server_turn(source.current.id, source.turn_id)
        source.apply_effect_damage(-7, 7, 50)
        before = a.snapshot(source)
        records = []
        factory, adapter = a.server_runtime(
            character, monsters, deck, action_id=2, rng=rng, critical=False
        )
        try:
            result = a.prepare_spell_transaction(
                struct.pack(
                    ">qqiih",
                    7,
                    (7 << 32) | spell,
                    *(cells[1] if spell == 5033 else center)
                ),
                character,
                source,
                3,
                deck,
                wp_current=source.actors[7].effect_stats[4],
                action_id=2,
                line_of_sight=lambda x, y, p: a.authoritative_visible(
                    1134,
                    x,
                    y,
                    p,
                    blocking_footprints={
                        i: {v.position[:2]} for i, v in p.actors.items() if v.hp > 0
                    },
                ),
                runtime_factory=a.observed(factory, records),
                conditional_context=lambda request, p: adapter.cast_condition(
                    p, request
                ),
            )
            rows.append(
                dict(
                    spell_id=spell,
                    level=level,
                    status="executed",
                    costs=result.plan["costs"],
                    actors=[
                        dict(
                            id=i,
                            cell=v.position,
                            hp_before=v.hp,
                            hp_after=result.fight.actors[i].hp,
                        )
                        for i, v in source.actors.items()
                    ],
                    armor_before={
                        i: v.effect_stats.get(97, 0) for i, v in source.actors.items()
                    },
                    armor_after={
                        i: v.effect_stats.get(97, 0)
                        for i, v in result.fight.actors.items()
                    },
                    packets=dict(collections.Counter(op for op, _ in result.packets)),
                    events=result.events,
                    rollback_preserved=a.snapshot(source) == before,
                    resource_before={
                        s: source.actors[7].effect_stats[s] for s in (2, 3, 4)
                    },
                    resource_after={
                        s: result.fight.actors[7].effect_stats[s] for s in (2, 3, 4)
                    },
                    false_conditions=[r for r in records if r[1] == "condition_false"],
                    execution_trace=records,
                )
            )
        except Exception as e:
            rows.append(
                dict(
                    spell_id=spell,
                    level=level,
                    status="rejected",
                    reason=str(e),
                    rollback_preserved=a.snapshot(source) == before,
                )
            )
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
    report = dict(
        rows=rows,
        sources_stable=before_hash == hashes(),
        fixture="Native map1134, own NPC5525 level1; initialized Zurcarák loses50HP through trusted effect damage before self cast. No healing state forced. Offline only.",
    )
    Path("docs/reports/combat-inventory/healing-flags-current.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )


if __name__ == "__main__":
    run()
