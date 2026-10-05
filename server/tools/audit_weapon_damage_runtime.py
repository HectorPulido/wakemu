#!/usr/bin/env python3
"""Offline owned12889 damage audit; real dispatcher, explicit unit-test LOS.

The fixture equips exactly one persisted item UID, constructs complete native
player/NPC snapshots, and uses the production weapon preparation function.
No selector, area, criterion, effect value or branch is overridden.
"""
import argparse
from collections import Counter
from copy import deepcopy
import datetime
import hashlib
import json
from pathlib import Path
from random import Random
import struct
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "server"), str(ROOT / "server/tests")]
from wakfu_server.combat_weapon import (
    catalog,
    weapon_runtime_catalog,
    prepare_server_weapon,
    DAMAGE_FAMILIES,
)
from wakfu_server.combat_actor_snapshot import build_player_snapshot, build_npc_snapshot
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_event_replay import NativeEventReplay
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.equipment import RULES
from wakfu_server.equipment_stats import effective_character, combat_resources
from wakfu_server.health import maximum
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck
from test_combat_weapon import equipped


def source_hashes():
    paths = list((ROOT / "server/wakfu_server").rglob("*.py"))
    paths += list((ROOT / "server/protocol").glob("*.json"))
    paths += list((ROOT / "server/protocol").glob("*.json.gz"))
    return {
        str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(paths)
    }


def damage_roots(rule, compiled):
    roots = tuple(
        row["reference"]
        for row in rule["roots"]
        if row["active"] and row["execution_mode"] == 2
    )
    return (
        roots
        if roots
        and all(
            compiled.effects[str(ref)]["effect_class"] in DAMAGE_FAMILIES
            and not compiled.effects[str(ref)].get("children")
            for ref in roots
        )
        else ()
    )


def target_cell(rule):
    minimum, maximum_range = rule["native_cpF"], rule["native_cpG"]
    distance = max(1, minimum) if maximum_range > 0 else 0
    if not minimum <= distance <= maximum_range:
        raise ValueError("No legal target in explicit axial unit fixture")
    return (distance, 0, 0)


def fixture(rule):
    cell = target_cell(rule)
    # This is owned test entity HP, supplied BEFORE native snapshot construction;
    # it is not assigned to a damage primitive or changed after snapshot install.
    npc_cell = cell if cell != (0, 0, 0) else (1, 0, 0)
    character = equipped(
        dict(
            id=7,
            account_id=3,
            map_id=1134,
            breed=11,
            level=200,
            hp=maximum(11, 200),
            max_hp=maximum(11, 200),
        ),
        rule["reference"],
    )
    character = effective_character(character)
    resources = combat_resources(character, base_initiative=10)
    caster = Actor(
        7,
        0,
        (0, 0, 0),
        character["hp"],
        resources["ap"],
        resources["mp"],
        resources["initiative"],
        200,
        3,
        True,
        max_hp=character["max_hp"],
    )
    npc = Actor(-7, 1, npc_cell, 100000, 6, 3, 5, 1, max_hp=100000)
    # Flat synthetic arena spans caster and target, with a margin for the native
    # area. All area and actor tests still run; this is not a client map/LOS test.
    cells = {(x, y, 0) for x in range(-8, cell[0] + 9) for y in range(-8, 9)}
    fight = Fight(78, [caster, npc], cells, {0: {caster.position}, 1: {npc.position}})
    fight.ready(3)
    caster.direction, npc.direction = 0, 3
    build_player_snapshot(
        character,
        caster,
        wp_current=resources["wp"],
        wp_maximum=resources["wp"],
        running_effects=(),
    ).install(caster)
    monster = dict(id=-7, ref=5525, map_id=1134)
    build_npc_snapshot(
        monster, npc, wp_current=0, wp_maximum=0, running_effects=()
    ).install(npc)
    fight.native_effect_uid_next = 1
    fight.native_obstacle_cells = frozenset()
    return character, monster, fight, cell


def rejection_category(reason):
    for fragment, category in (
        ("Unsupported owned equipment", "missing_equipped_stat_support"),
        ("Unsupported equipment", "missing_equipped_stat_support"),
        ("native equipment", "equipment_gate"),
        ("native maximum HP", "equipment_snapshot_gate"),
        ("Insufficient authoritative weapon resources", "insufficient_resources"),
        ("native range", "range_gate"),
        ("native weapon USE", "missing_use_criterion"),
        ("QI.P", "missing_terrain_gate"),
        ("native area", "missing_area"),
        ("Missing", "missing_native_context"),
        ("Unaudited", "unaudited_native_context"),
        ("Unsupported", "unsupported_native_context"),
    ):
        if fragment.lower() in reason.lower():
            return category
    return "runtime_rejection"


def dynamic_damage_inventory(compiled):
    from wakfu_server.spell_audit import catalog as spell_catalog
    from wakfu_server.spells import SPELLS
    from wakfu_server.combat_class_initialization import BREEDS
    from wakfu_server.combat_parameters import parameter_value

    exported = spell_catalog()
    states = compiled.source_states["states"]
    names = {
        row["id"]: row["name"]
        for row in json.loads((ROOT / "server/protocol/spell-names.json").read_text())[
            "spells"
        ]
    }
    result, reachable = [], set()
    definitions = [
        (dict(row), exported["spells"].get(str(row["id"])))
        for row in SPELLS.values()
        if row["breed"] in (16, 19)
    ]
    for breed in (16, 19):
        innate_roots = [
            ref
            for state in BREEDS[breed]["innate_states"]
            for ref in states[str(state["reference"])]["effect_ids"]
        ]
        definitions.append(
            (
                dict(id=None, breed=breed, kind="innate", unlock_level=1),
                dict(levels=[[0, 0, innate_roots]]),
            )
        )
    for definition, tree in definitions:
        if tree is None:
            continue
        pending = [(ref, []) for level in tree["levels"] for ref in level[2]]
        seen, matches = set(), []
        while pending:
            reference, path = pending.pop()
            if reference in seen:
                continue
            seen.add(reference)
            effect = compiled.effects.get(str(reference))
            if effect is None:
                continue
            edge = dict(
                reference=reference,
                family=effect["effect_class"],
                criteria=effect.get("criteria"),
                flags=list(effect.get("native_effect_flags", ())),
                execution_mode=effect.get("native_execution_mode"),
            )
            path = path + [edge]
            if effect["effect_class"] in (917, 1083):
                reachable.add(reference)
                matches.append(
                    dict(reference=reference, family=effect["effect_class"], path=path)
                )
            pending.extend((ref, path) for ref in effect.get("children", ()))
            if effect["effect_class"] == 304 and effect["parameter_count"]:
                # Conservative static reachability, not runtime guard bypass.
                refs = {
                    parameter_value(effect["parameters"], 0, level)
                    for level in range(251)
                }
                for state_ref in refs:
                    state_ref = ((state_ref + 32768) % 65536) - 32768
                    state = states.get(str(state_ref))
                    if state is not None:
                        state_path = path + [dict(state_reference=state_ref)]
                        pending.extend((ref, state_path) for ref in state["effect_ids"])
        if matches:
            result.append(
                dict(
                    spell_id=definition["id"],
                    name=names.get(definition["id"]),
                    breed=definition["breed"],
                    kind=definition["kind"],
                    unlock_level=definition["unlock_level"],
                    effects=sorted(matches, key=lambda row: row["reference"]),
                )
            )
    exported_effects = [
        dict(reference=int(ref), family=effect["effect_class"])
        for ref, effect in compiled.effects.items()
        if effect["effect_class"] in (917, 1083)
    ]
    return dict(
        registry=dict(STASIS=917, LIGHT=1083),
        scope="Installed class spell roots, innates, child graphs and reachable state304 roots. All exported levels/state-reference expressions considered; criteria/flags/modes preserved in paths. Static reachability is not evidence of runtime eligibility or current retail behavior.",
        class_spells=result,
        exported_definition_counts=dict(
            Counter(row["family"] for row in exported_effects)
        ),
        not_reachable_from_these_class_sources=[
            row for row in exported_effects if row["reference"] not in reachable
        ],
    )


def summarize_rows(rows):
    by_item = {}
    unsupported = Counter()
    for row in rows:
        by_item.setdefault(row["item_reference"], []).append(row)
        if row.get("rejection_category") == "missing_equipped_stat_support":
            detail = json.loads(row["reason"].split(": ", 1)[1])
            unsupported.update(effect.get("generic") for effect in detail["effects"])
    return dict(
        items_passing_both_branches=sum(
            len(cases) == 2 and all(row["status"] == "PASS" for row in cases)
            for cases in by_item.values()
        ),
        items_with_any_verified_damage=sum(
            any(row["status"] == "PASS" for row in cases) for cases in by_item.values()
        ),
        rollback_verified_cases=sum(
            row["rollback_preserved"] and "source_uid_next" in row for row in rows
        ),
        no_source_mutation_flags=sum(row["rollback_preserved"] for row in rows),
        checkpoints_compared_after_prepare=sum(
            "source_uid_next" in row for row in rows
        ),
        setup_rejected_before_checkpoint=sum(
            row.get("rejected_before_snapshot", False) for row in rows
        ),
        equipment_level_cases_not_executed=sum(
            row.get("not_executed", False) for row in rows
        ),
        unsupported_equipment_generic_occurrences=dict(unsupported),
    )


def run(output, references=None):
    before_hashes = source_hashes()
    rules, compiled = catalog(), weapon_runtime_catalog()  # one cached load
    candidates = [(rule, damage_roots(rule, compiled)) for rule in rules.values()]
    excluded = [rule["reference"] for rule, roots in candidates if not roots]
    candidates = sorted(
        ((rule, roots) for rule, roots in candidates if roots),
        key=lambda pair: pair[0]["reference"],
    )
    if references is not None:
        candidates = [
            (rule, roots)
            for rule, roots in candidates
            if rule["reference"] in references
        ]
    rows, deliveries = [], []
    original_replay = NativeEventReplay.__call__

    def observe_replay(self, source, *args, **kwargs):
        deliveries.append(
            dict(
                uid=source.uid,
                reference=source.generic_effect,
                value=source.value,
                channel=source.channel,
                manager_actor_id=source.manager_actor_id,
                events=list(source.event_ids),
            )
        )
        return original_replay(self, source, *args, **kwargs)

    NativeEventReplay.__call__ = observe_replay
    try:
        for number, (rule, roots) in enumerate(candidates, 1):
            requirement = RULES.get(rule["reference"], {}).get("minimum_level")
            for critical in (False, True):
                row = dict(
                    item_reference=rule["reference"],
                    name=rule.get("name"),
                    item_level=rule["item_level"],
                    minimum_equipment_level=requirement,
                    actor_level=200,
                    critical=critical,
                    root_references=list(roots),
                    gameplay_verified=False,
                )
                if type(requirement) is not int or requirement > 200:
                    row.update(
                        status="LIMITED",
                        rejection_category="actor_level_above_supported_200"
                        if type(requirement) is int
                        else "missing_equipment_level",
                        reason="Production character health/snapshot supports levels1..200; no mismatched actor200/character245 fixture is fabricated.",
                        rollback_preserved=True,
                        not_executed=True,
                    )
                    rows.append(row)
                    continue
                deliveries.clear()
                fight = None
                try:
                    character, monster, fight, cell = fixture(rule)
                    prior = snapshot(fight)
                    transaction = prepare_server_weapon(
                        struct.pack(">qqbiih", 7, 1000, 15, *cell),
                        character,
                        {-7: monster},
                        fight,
                        3,
                        encode_deck((), ()),
                        action_id=1,
                        line_of_sight=lambda *args: True,
                        critical=critical,
                        rng=Random(1),
                    )
                    after = transaction.fight
                    hp_delta = fight.actors[-7].hp - after.actors[-7].hp
                    damage_packets = []
                    for opcode, packet in transaction.packets:
                        if opcode == 12613 and len(packet) >= 19:
                            family = struct.unpack_from(">i", packet, 13)[0]
                            if family in DAMAGE_FAMILIES:
                                identity = _identity_fields(packet[19:])
                                for actor_field in (6, 7):
                                    if identity.get(actor_field, 0) >= (1 << 63):
                                        identity[actor_field] -= 1 << 64
                                damage_packets.append(
                                    dict(
                                        family=family,
                                        uid=identity.get(1),
                                        reference=identity.get(3),
                                        value=identity.get(4),
                                        caster_id=identity.get(6),
                                        target_id=identity.get(7),
                                    )
                                )
                    cost_exact = all(
                        before - current == transaction.plan["costs"][name]
                        for name, before, current in (
                            ("ap", fight.actors[7].ap, after.actors[7].ap),
                            ("mp", fight.actors[7].mp, after.actors[7].mp),
                            (
                                "wp",
                                fight.actors[7].effect_stats[4],
                                after.actors[7].effect_stats[4],
                            ),
                        )
                    )
                    target_damage = [
                        packet for packet in damage_packets if packet["target_id"] == -7
                    ]
                    passed = (
                        hp_delta > 0
                        and bool(target_damage)
                        and bool(deliveries)
                        and cost_exact
                    )
                    row.update(
                        status="PASS" if passed else "NO_DAMAGE_VERIFIED",
                        target_cell=list(cell),
                        hp_before=fight.actors[-7].hp,
                        hp_after=after.actors[-7].hp,
                        target_hp_delta=hp_delta,
                        caster_hp_delta=fight.actors[7].hp - after.actors[7].hp,
                        costs=transaction.plan["costs"],
                        exact_resource_spend=cost_exact,
                        damage_packets=damage_packets,
                        native_event_deliveries=list(deliveries),
                        packet_opcodes=dict(
                            Counter(opcode for opcode, _ in transaction.packets)
                        ),
                        fight_events=list(transaction.events),
                        outcomes=list(transaction.outcomes),
                        rollback_preserved=snapshot(fight) == prior,
                        source_uid_next=fight.native_effect_uid_next,
                        preview_uid_next=after.native_effect_uid_next,
                        gameplay_verified=passed,
                    )
                except Exception as error:
                    row.update(
                        status="REJECT",
                        reason=str(error),
                        rejection_category=rejection_category(str(error)),
                        exception_type=type(error).__name__,
                        traceback=traceback.format_exc(),
                        rollback_preserved=fight is None or snapshot(fight) == prior,
                        rejected_before_snapshot=fight is None,
                    )
                if not row["rollback_preserved"]:
                    row["status"] = "INVARIANT_FAILURE"
                    row["gameplay_verified"] = False
                rows.append(row)
            if number % 50 == 0 or number == len(candidates):
                print(
                    json.dumps(
                        dict(
                            items_completed=number,
                            total_items=len(candidates),
                            counts=dict(Counter(row["status"] for row in rows)),
                        )
                    ),
                    flush=True,
                )
    finally:
        NativeEventReplay.__call__ = original_replay
    after_hashes = source_hashes()
    report = dict(
        created_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        all_weapon_definitions=len(rules),
        direct_damage_candidates=len(candidates),
        non_damage_definitions_excluded=excluded,
        rows=rows,
        installed_dynamic_damage_sources=dynamic_damage_inventory(compiled),
        counts=dict(Counter(row["status"] for row in rows)),
        rejection_categories=dict(
            Counter(
                row.get("rejection_category")
                for row in rows
                if row.get("rejection_category")
            )
        ),
        sources_stable=before_hashes == after_hashes,
        changed_sources=[
            path
            for path in sorted(set(before_hashes) | set(after_hashes))
            if before_hashes.get(path) != after_hashes.get(path)
        ],
        source_hashes=before_hashes,
        fixture=dict(
            caster="Owned Sacrógrito200, equipped UID1000 slot15, actual item bonuses; native resource computation, no fabricated AP/WP",
            target="Owned NPC5525 level1 with explicit live HP/maxHP100000 before native snapshot construction; complete ffC/ffx snapshot; synthetic high-health test entity",
            terrain="Synthetic flat axial arena with margin8, normal exported area/selector execution",
            los="Unit fixture callback returnsTrue; no GUI or native map LOS coverage",
            deck="Empty; damage coverage isolates weapon roots, no passive claims",
            branch="Both explicit criticalFalse and criticalTrue, native item template level, Random(1) per private case",
        ),
        limitations=[
            "Not a GUI/client animation acknowledgement test.",
            "PASS requires target HP loss, actual damage packet, lifecycle delivery and exact resource spend, not actor_state_changed.",
            "Equipment above supported character level200 is listed individually without mismatched level fabrication.",
            "Fixture-creation rejections and level limitations do not execute prepare_server_weapon or compare an existing Fight checkpoint; their no-source-mutation flag is vacuous and listed separately.",
            "Results cover one legal axial target and ordinary living actor context; other contexts are not exhaustively covered.",
        ],
    )
    report["summary"] = summarize_rows(rows)
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                key: report[key]
                for key in (
                    "counts",
                    "rejection_categories",
                    "sources_stable",
                    "changed_sources",
                )
            }
        ),
        flush=True,
    )
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        default="docs/reports/combat-inventory/weapon-damage-runtime-audit.json",
    )
    parser.add_argument("--references", type=int, nargs="+")
    args = parser.parse_args()
    run(args.output, None if args.references is None else set(args.references))
