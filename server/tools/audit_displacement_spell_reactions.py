#!/usr/bin/env python3
"""Real common cast/initialization and displacement reactions, offline native map.

No GUI validation. Fixture uses original NPC stats and legal cast cells; sources
are checkpointed before every transaction. Optional second spell tests reactions.
"""
import json
import copy
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_active_spells as native
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


def observe(fight):
    return {
        str(i): dict(
            hp=a.hp,
            armor=a.effect_stats[97],
            position=list(a.position),
            states=[
                dict(reference=e.reference, level=e.level, uid=e.uid)
                for e in a.state_ledger.entries
            ],
        )
        for i, a in fight.actors.items()
    }


def run(
    *,
    scenarios=None,
    output_name="docs/reports/combat-inventory/cinetosis-fulgor-runtime-audit.json"
):
    scenarios = scenarios or (
        (5041, "normal", 5030, False),
        (5041, "berserker", 5030, False),
        (5030, "without_state", 5030, False),
        (5042, "normal", 5030, False),
    )
    before_hash = native.init.source_hashes()
    definitions = native.catalog()
    origin = (-8, -7, -1)
    terrain = native.bounded_arena(
        native.map_geometry(1134), origin, [(-7, -7, -1)], radius=12
    )
    rows = []
    for spell, scenario, followup, critical in scenarios:
        for level in (max(20, native.SPELLS[spell]["unlock_level"]), 200):
            candidates = dict(
                native.target_candidates(
                    definitions["spells"][str(spell)], level, terrain, origin
                )
            )
            variant = "enemy" if spell in (5041, 5030) else "empty_cell"
            cell = candidates[variant]
            enemy = (
                cell
                if variant == "enemy"
                else next(
                    c for c in sorted(terrain["cells"]) if c not in (origin, cell)
                )
            )
            character, monster, base = native.fixture(
                11,
                level,
                enemy,
                terrain,
                origin,
                monster_reference=3646,
                monster_level=12,
                ready=False,
            )
            monsters = {monster["id"]: monster}
            if scenario == "push_zone":
                from wakfu_server.combat_state_ledger import StateLedger

                choices = [
                    (enemy[0] + dx, enemy[1] + dy, enemy[2])
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    if (enemy[0] + dx, enemy[1] + dy, enemy[2]) in terrain["cells"]
                    and (enemy[0] + 2 * dx, enemy[1] + 2 * dy, enemy[2])
                    in terrain["cells"]
                    and (enemy[0] + dx, enemy[1] + dy, enemy[2]) != origin
                ]
                adjacent = choices[0]
                actor = copy.deepcopy(base.actors[-7])
                actor.id, actor.position, actor.state_ledger = (
                    -8,
                    adjacent,
                    StateLedger(-8),
                )
                actor.turn_count = 0
                base.actors[-8] = actor
                base.placement[1].add(adjacent)
                monsters[-8] = dict(
                    monster, id=-8, x=adjacent[0], y=adjacent[1], z=adjacent[2]
                )
            base.ready(3)
            if scenario == "berserker":
                base.apply_effect_damage(-7, 7, base.actors[7].max_hp * 2 // 3)
                character["hp"] = base.actors[7].hp
            deck = encode_deck(list(dict.fromkeys([spell, followup])))
            rng = random.Random(0)
            initialization_before = snapshot(base)
            try:
                source, _ = prepare_server_initialization(
                    character,
                    monsters,
                    base,
                    3,
                    deck,
                    action_id=1,
                    rng=rng,
                    fight_start=True,
                )
            except Exception as error:
                rows.append(
                    dict(
                        spell_id=spell,
                        level=level,
                        scenario=scenario,
                        critical=critical,
                        followup=followup,
                        status="initialization_rejected",
                        reason=str(error),
                        error_type=type(error).__name__,
                        rollback_preserved=snapshot(base) == initialization_before,
                        before=observe(base),
                        gameplay_verified=False,
                    )
                )
                continue
            while source.current.id != 7:
                source.end_server_turn(source.current.id, source.turn_id)
            source_before = snapshot(source)
            row = dict(
                spell_id=spell,
                level=level,
                scenario=scenario,
                critical=critical,
                followup=followup,
                variant=variant,
                cell=cell,
                before=observe(source),
                gameplay_verified=False,
            )

            def los(a, b, p):
                return authoritative_visible(
                    1134,
                    a,
                    b,
                    p,
                    blocking_footprints={
                        actor.id: {actor.position[:2]}
                        for actor in p.actors.values()
                        if actor.hp > 0
                    },
                )

            try:
                result = prepare_server_spell(
                    native.struct.pack(">qqiih", 7, (7 << 32) | spell, *cell),
                    character,
                    monsters,
                    source,
                    3,
                    deck,
                    action_id=2,
                    line_of_sight=los,
                    critical=critical,
                    rng=rng,
                )
                row.update(
                    after=observe(result.fight),
                    costs=result.plan["costs"],
                    outcomes=repr(result.outcomes),
                    packets=[op for op, _ in result.packets],
                    events=list(result.events),
                    rollback_preserved=snapshot(source) == source_before,
                )
                if spell == 5041:
                    current = result.fight
                    current_before = snapshot(current)
                    target = current.actors[-7].position
                    next_result = prepare_server_spell(
                        native.struct.pack(">qqiih", 7, (7 << 32) | followup, *target),
                        character,
                        monsters,
                        current,
                        3,
                        deck,
                        action_id=3,
                        line_of_sight=los,
                        critical=critical,
                        rng=rng,
                    )
                    row.update(
                        after_pull=observe(next_result.fight),
                        pull_costs=next_result.plan["costs"],
                        pull_events=list(next_result.events),
                        pull_rollback_preserved=snapshot(current) == current_before,
                    )
                row["status"] = "executed"
            except Exception as error:
                row.update(
                    status="rejected",
                    reason=str(error),
                    error_type=type(error).__name__,
                    rollback_preserved=snapshot(source) == source_before,
                )
            rows.append(row)
    result = dict(
        cases=rows,
        sources_stable=before_hash == native.init.source_hashes(),
        source_hashes=before_hash,
        fixture="Native map1134 topology/LOS; NPC3646 level12 original HP; bare Sacro; native RNG seed0; no GUI",
    )
    output = Path(output_name)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(
        json.dumps(
            dict(sources_stable=result["sources_stable"], cases=rows),
            ensure_ascii=False,
        )
    )
    return result


if __name__ == "__main__":
    run()
