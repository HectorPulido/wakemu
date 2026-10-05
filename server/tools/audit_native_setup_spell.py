"""Audit an original setup-root graph on a private preview (not a client cast).

A missing native grant is not fabricated: this exposes the next execution
blocker in the source graph and cannot claim request ownership/readiness.
"""
import argparse, copy, json, random
from pathlib import Path
import audit_active_spells as audit
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    server_runtime,
)
from wakfu_server.combat_native_spell_casting import catalog
from wakfu_server.combat_effect_dispatch import EffectInvocation
from wakfu_server.spells import encode_deck, SPELLS
from wakfu_server.fight_checkpoint_store import snapshot


def run(producer, levels, deck, output):
    before_hash = audit.init.source_hashes()
    rows = []
    geometry = audit.map_geometry(1134)
    origin = (-8, -7, -1)
    seed = (-7, -7, -1)
    terrain = audit.bounded_arena(geometry, origin, [seed], radius=12)
    for level in levels:
        character, monster, fight = audit.fixture(2, level, seed, terrain, origin)
        unavailable = [ref for ref in deck if SPELLS[ref]["unlock_level"] > level]
        if unavailable:
            rows.append(
                dict(
                    level=level,
                    status="legitimate_setup_unavailable",
                    unavailable_deck=unavailable,
                    rollback_preserved=True,
                )
            )
            continue
        deck_blob = encode_deck(
            [ref for ref in deck if SPELLS[ref]["kind"] == "active"],
            [ref for ref in deck if SPELLS[ref]["kind"] == "passive"],
        )
        source, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck_blob,
            action_id=1,
            rng=random.Random(0),
            fight_start=True,
        )
        source.apply_effect_damage(-7, 7, min(100, source.actors[7].hp - 1))
        before = snapshot(source)
        preview = copy.deepcopy(source)
        factory, _ = server_runtime(
            character,
            {-7: monster},
            deck_blob,
            action_id=2,
            critical=False,
            rng=random.Random(0),
        )
        records = []
        dispatcher, packets = audit.observed(factory, records)(
            preview, dict(spell_id=producer, evaluation_level=level)
        )
        cell = next(
            c
            for c in sorted(terrain["cells"])
            if c not in (origin, seed)
            and 1 <= abs(c[0] - origin[0]) + abs(c[1] - origin[1]) <= 4
        )
        roots = catalog()[str(producer)]["levels"][level - 1][2]
        row = dict(
            level=level,
            producer=producer,
            deck=deck,
            roots=roots,
            cell=cell,
            setup_policy="Original root execution only; no fabricated client grant or condition/state override",
        )
        try:
            with preview.effect_resolution():
                outcomes = [
                    dispatcher.execute(EffectInvocation(ref, level, 7, None, cell))
                    for ref in roots
                ]
            row.update(
                status="root_graph_executed",
                outcomes=outcomes,
                retained_states=[
                    s.reference for s in preview.actors[7].state_ledger.entries
                ],
            )
        except Exception as error:
            ref = getattr(error, "audit_reference", None)
            row.update(
                status="setup_blocked",
                reason=str(error),
                reference=ref,
                effect_class=(factory.effects.get(str(ref)) or {}).get("effect_class"),
            )
        row.update(
            rollback_preserved=snapshot(source) == before,
            executed_reference_count=len(records),
        )
        rows.append(row)
    report = dict(
        rows=rows,
        sources_stable=before_hash == audit.init.source_hashes(),
        limitations=[
            "Direct root graph audit does not establish client access to setup spell or a completed summon."
        ],
    )
    Path(output).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("producer", type=int)
    parser.add_argument("levels", type=int, nargs="+")
    parser.add_argument("--deck", type=int, nargs="+", required=True)
    parser.add_argument("--output", required=True)
    a = parser.parse_args()
    run(a.producer, a.levels, a.deck, a.output)
