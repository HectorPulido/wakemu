#!/usr/bin/env python3
"""Offline owned class summon casts with exact native descriptor provenance.

This is a fixture execution audit, not proof that creation criteria hold in a
live class turn. No actor resources, control flags or target states are added
to make a cast succeed. One process owns all runtime catalogs.
"""
import argparse
import copy
import hashlib
import json
import random
import struct
from pathlib import Path

from audit_active_spells import fixture
from wakfu_server.combat_arena_selection import bounded_arena
from wakfu_server.spells import encode_deck
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.combat_spell_transaction import prepare_spell_transaction
from wakfu_server.combat_summon import SummonSpecification, fresh_summon_insertion
from wakfu_server.combat_summon_creation import NativeSummonBuilder
from wakfu_server.combat_summon_spellbook import profile_abilities
from wakfu_server.combat_terrain import map_geometry
from wakfu_server.fight_checkpoint_store import snapshot


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(native_path, output):
    source_hash = digest(native_path)
    native = json.loads(native_path.read_text())
    samples = {}

    def rank(sample):
        level = sample["context"]["caster_level"]
        return (
            not 1 <= level <= 200,
            bool(sample["native_property_counters"].get("101", 0)),
        )

    for reference, effect in native["effects"].items():
        for sample in effect["evaluations"]:
            if sample["descriptor_created"]:
                descriptor = sample["descriptor"]
                key = descriptor["reference"], descriptor["level"]
                previous = samples.get(key)
                if previous is None or rank(sample) < rank(previous[1]):
                    samples[key] = int(reference), sample
    origin, enemy = (-8, -7, -1), (-7, -7, -1)
    terrain = bounded_arena(map_geometry(1134), origin, [enemy], radius=12)
    summon_cell = min(
        (cell for cell in terrain["cells"] if cell not in (origin, enemy)),
        key=lambda cell: (abs(cell[0] - origin[0]) + abs(cell[1] - origin[1]), cell),
    )
    deck = encode_deck([])
    rows = []
    for profile, metadata in sorted(
        profile_abilities().items(), key=lambda item: int(item[0])
    ):
        profile = int(profile)
        maximum = max(
            (ability["maximum_level"] for ability in metadata["abilities"]), default=245
        )
        for requested in sorted({0, 1, 20, 200, maximum}):
            seed = samples.get((profile, requested))
            base = dict(
                profile=profile,
                descriptor_level=requested,
                scope="native fresh descriptor fixture",
                fixture_owner_breed=2,
                gameplay_verified=False,
            )
            if seed is None:
                rows.append(
                    dict(
                        base,
                        stage="descriptor",
                        status="missing_native_descriptor_sample",
                    )
                )
                continue
            effect_reference, sample = seed
            base["descriptor_effect_reference"] = effect_reference
            base["native_descriptor_context"] = sample["context"]
            base["native_property_counters"] = sample["native_property_counters"]
            base["descriptor_transforms_executed"] = False
            if not 1 <= sample["context"]["caster_level"] <= 200:
                rows.append(
                    dict(
                        base,
                        stage="owner_domain",
                        status="skipped_unreachable_owner_context",
                        reason="Native sample caster level is outside actual player domain 1..200",
                    )
                )
                continue
            if sample["native_property_counters"].get("101", 0):
                rows.append(
                    dict(
                        base,
                        stage="creation",
                        status="rejected",
                        reason="Native descriptor property101 requires owned visual-copy producer",
                    )
                )
                continue
            try:
                character, creature, fight = fixture(
                    2, sample["context"]["caster_level"], enemy, terrain, origin
                )
                fight.actors[character["id"]].direction = sample["context"][
                    "caster_direction"
                ]
                factory, adapter = server_runtime(
                    character,
                    {creature["id"]: creature},
                    deck,
                    action_id=1,
                    critical=False,
                    rng=random.Random(0),
                )
                descriptor = sample["descriptor"]
                anchors = {
                    "EFFECT_CASTER": "caster",
                    "CURRENT": "current",
                    "START": "start",
                }
                specification = SummonSpecification(
                    profile,
                    requested,
                    sample["self_controlled"],
                    sample["context"]["caster_direction"]
                    if descriptor["direction"] == -1
                    else descriptor["direction"],
                    sample["context"]["caster_team"]
                    if descriptor["team"] == -1
                    else descriptor["team"],
                    anchors[sample["timeline"]["anchor"]],
                    sample["timeline"]["offset"],
                )
                # Builder calls real profile statistics and owner authority.
                actor, registration = NativeSummonBuilder(adapter.actor_authority)(
                    fight, specification, character["id"], 901, summon_cell
                )
                if 114 in registration.fight_properties:
                    order, index = list(fight.order), fight.turn_index
                else:
                    order, index = fresh_summon_insertion(
                        fight, specification, caster_id=character["id"], actor_id=901
                    )
                adapter.actor_authority.register(
                    fight, actor, registration, new_order=order, new_turn_index=index
                )
                if actor.id not in fight.order:
                    rows.append(
                        dict(
                            base,
                            stage="timeline",
                            status="not_present_in_native_timeline",
                        )
                    )
                    continue
                # Advance through actual turn producers, including the native
                # actor turn count used by effect timers; never synthesize it.
                passed = []
                while fight.current.id != actor.id:
                    current = fight.current
                    passed.append(current.id)
                    if current.controlled:
                        fight.end_turn(current.owner_id, current.id, current.turn_count)
                    else:
                        fight.end_server_turn(current.id, fight.turn_id)
                    if len(passed) > len(fight.order):
                        raise AssertionError("Registered summon turn is unreachable")
                base["passed_actual_turns"] = passed
                base["actual_summon_turn_count"] = actor.turn_count
            except Exception as error:
                rows.append(
                    dict(
                        base,
                        stage="creation",
                        status="rejected",
                        error_type=type(error).__name__,
                        reason=str(error),
                    )
                )
                continue
            if not actor.native_summon_action_book["actions"]:
                rows.append(dict(base, stage="book", status="native_empty_action_book"))
            for action in actor.native_summon_action_book["actions"]:
                row = dict(
                    base,
                    ability_reference=action["reference"],
                    casting_uid=action["uid"],
                    evaluation_level=action["level"],
                    ap=actor.ap,
                    mp=actor.mp,
                    wp=actor.effect_stats[4],
                    attempts=[],
                )
                # These are explicit target fixtures, not a complete condition map.
                candidates = list(dict.fromkeys([summon_cell, origin, enemy]))
                for cell in candidates:
                    source = copy.deepcopy(fight)
                    before = snapshot(source)
                    body = struct.pack(">qqiih", actor.id, action["uid"], *cell)
                    try:
                        transaction = prepare_spell_transaction(
                            body,
                            character,
                            source,
                            3,
                            deck,
                            wp_current=actor.effect_stats[4],
                            action_id=1,
                            line_of_sight=None,
                            runtime_factory=factory,
                            conditional_context=lambda request, preview: adapter.cast_condition(
                                preview, request
                            ),
                            critical=False,
                        )
                        attempt = dict(
                            target=list(cell),
                            status="prepared_transaction",
                            packet_count=len(transaction.packets),
                        )
                    except Exception as error:
                        attempt = dict(
                            target=list(cell),
                            status="rejected",
                            error_type=type(error).__name__,
                            reason=str(error),
                        )
                    if snapshot(source) != before:
                        raise AssertionError(
                            "Owned cast audit mutated its transaction source"
                        )
                    row["attempts"].append(attempt)
                rows.append(row)
    if digest(native_path) != source_hash:
        raise AssertionError("Native descriptor source changed during audit")
    expected_references = sorted(
        {
            ability["reference"]
            for profile in profile_abilities().values()
            for ability in profile["abilities"]
        }
    )
    attempted_references = sorted(
        {row["ability_reference"] for row in rows if "ability_reference" in row}
    )
    report = dict(
        native_source=str(native_path),
        native_sha256=source_hash,
        static_profile_count=len(profile_abilities()),
        expected_ability_references=expected_references,
        attempted_ability_references=attempted_references,
        missing_ability_references=sorted(
            set(expected_references) - set(attempted_references)
        ),
        gameplay_verified=False,
        rows=rows,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--native", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.native, args.output)
