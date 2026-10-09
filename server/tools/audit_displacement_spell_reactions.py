#!/usr/bin/env python3
"""Real common cast/initialization and displacement reactions, offline native map.

No GUI validation. Fixture uses original NPC stats and legal cast cells; sources
are checkpointed before every transaction. Optional second spell tests reactions.
"""
import json
import copy
import random
import sys
from importlib import import_module
from unittest.mock import patch
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import audit_active_spells as native
from combat_audit_turns import advance_actual_turn
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
    prepare_server_turn_end,
    prepare_server_turn_start,
    server_runtime,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.spells import encode_deck
from wakfu_server.fight_checkpoint_store import snapshot


def observe(fight):
    return {
        str(i): dict(
            hp=a.hp,
            max_hp=a.max_hp,
            stats=dict(a.effect_stats),
            virtual_hp_max=a.effect_maxima[92],
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
    native_casting = native.native_casting_catalog()
    origin = (-8, -7, -1)
    terrain = native.bounded_arena(
        native.map_geometry(1134), origin, [(-7, -7, -1)], radius=12
    )
    rows = []
    for spell, scenario, followup, critical in scenarios:
        for level in (max(20, native.SPELLS[spell]["unlock_level"]), 200):
            candidates = dict(
                native.target_candidates(
                    definitions["spells"][str(spell)],
                    level,
                    terrain,
                    origin,
                    native=native.native_casting_baseline(
                        native_casting[str(spell)], level
                    ),
                    spell_reference=spell,
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
            deck = encode_deck(
                list(
                    dict.fromkeys(
                        [spell, followup] + ([5028] if scenario == "berserker" else [])
                    )
                )
            )
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
            turn_runtime = RuntimeMessages(
                source,
                turn_end_provider=lambda preview, **boundary: prepare_server_turn_end(
                    character, monsters, preview, deck, rng=rng, **boundary
                ),
                turn_start_provider=lambda preview, **boundary: prepare_server_turn_start(
                    character, monsters, preview, deck, rng=rng, **boundary
                ),
                expiration_runtime_factory=lambda *, action_id: server_runtime(
                    character,
                    monsters,
                    deck,
                    action_id=action_id,
                    critical=False,
                    rng=rng,
                )[0],
            )
            while turn_runtime.fight.current.id != 7:
                advance_actual_turn(turn_runtime)
            source = turn_runtime.fight

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

            preparation_casts = []
            if scenario == "berserker":
                # Real Blood for Blood self-loss after actual innate registration.
                # Empty legal recipients preserve the original NPC HP for the chain.
                for attempt in range(12):
                    if any(
                        entry.reference == 9315
                        for entry in source.actors[7].state_ledger.entries
                    ):
                        break
                    prepared = None
                    for candidate in sorted(terrain["cells"]):
                        if candidate in (
                            source.actors[7].position,
                            source.actors[-7].position,
                        ):
                            continue
                        try:
                            prepared = prepare_server_spell(
                                native.struct.pack(
                                    ">qqiih", 7, (7 << 32) | 5028, *candidate
                                ),
                                character,
                                monsters,
                                source,
                                3,
                                deck,
                                action_id=10 + attempt * 4,
                                line_of_sight=los,
                                critical=False,
                                rng=rng,
                            )
                            break
                        except ValueError:
                            continue
                    if prepared is None:
                        raise ValueError(
                            "No legal owned Blood for Blood preparation recipient"
                        )
                    previous_hp = source.actors[7].hp
                    source = prepared.fight
                    preparation_casts.append(
                        dict(
                            reference=5028,
                            cell=candidate,
                            before_hp=previous_hp,
                            after_hp=source.actors[7].hp,
                        )
                    )
                    turn_runtime.fight = source
                    advance_actual_turn(turn_runtime)
                    while (
                        turn_runtime.fight.phase == "active"
                        and turn_runtime.fight.current.id != 7
                    ):
                        advance_actual_turn(turn_runtime)
                    source = turn_runtime.fight
                if not any(
                    entry.reference == 9315
                    for entry in source.actors[7].state_ledger.entries
                ):
                    raise ValueError(
                        "Actual Blood for Blood and turn-start did not produce9315"
                    )
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
                preparation_casts=preparation_casts,
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
                    damage_calculations = []
                    damage_module = import_module(
                        prepare_server_spell.__module__.rsplit(".", 1)[0]
                        + ".combat_damage_handler"
                    )
                    calculate_damage = damage_module.damage_amount
                    consume_damage = damage_module.consume_damage
                    damage_consumptions = []

                    def observe_damage(
                        base, element, source_stats, target_stats, **context
                    ):
                        amount = calculate_damage(
                            base, element, source_stats, target_stats, **context
                        )
                        damage_calculations.append(
                            dict(
                                base=base,
                                element=element,
                                source_stats=dict(source_stats),
                                target_stats=dict(target_stats),
                                coefficient_mask=context["coefficient_mask"],
                                arithmetic_context=dict(context["arithmetic_context"]),
                                amount=amount,
                            )
                        )
                        return amount

                    def observe_consumption(value, **context):
                        consumed = consume_damage(value, **context)
                        damage_consumptions.append(
                            dict(
                                value=value,
                                context=dict(context),
                                result=dict(consumed),
                            )
                        )
                        return consumed

                    with patch.object(
                        damage_module, "damage_amount", side_effect=observe_damage
                    ), patch.object(
                        damage_module, "consume_damage", side_effect=observe_consumption
                    ):
                        next_result = prepare_server_spell(
                            native.struct.pack(
                                ">qqiih", 7, (7 << 32) | followup, *target
                            ),
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
                        damage_calculations=damage_calculations,
                        damage_consumptions=damage_consumptions,
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
