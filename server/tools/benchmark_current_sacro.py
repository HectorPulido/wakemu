"""One offline process: prewarm, current own Sacro deck, and cast regression."""
import time, json, random, struct, unittest, sys
from pathlib import Path
import audit_active_spells as audit
from wakfu_server.combat_server_spell import (
    prewarm_runtime_catalogs,
    prepare_server_initialization,
    prepare_server_spell,
    server_runtime,
)
from wakfu_server.spells import encode_deck
from wakfu_server.combat_los import authoritative_visible


def measured(label, callback):
    start = time.perf_counter()
    try:
        value = callback()
        row = {
            "label": label,
            "seconds": time.perf_counter() - start,
            "status": "returned",
        }
    except ValueError as error:
        value = None
        row = {
            "label": label,
            "seconds": time.perf_counter() - start,
            "status": "rejected",
            "reason": str(error),
        }
    print(json.dumps(row), flush=True)
    rows.append(row)
    return value


rows = []
sources = audit.init.source_hashes()
measured("prewarm", prewarm_runtime_catalogs)
geometry = audit.map_geometry(1134)
origin = (-8, -7, -1)
target = (-9, -7, -1)
terrain = audit.bounded_arena(geometry, origin, [target], radius=12)
character, monster, fight = audit.fixture(11, 20, target, terrain, origin)
deck = encode_deck([5028, 5029, 5030, 5031, 5033, 5034, 5038], [5051], -1)
monsters = {-7: monster}
initialized = measured(
    "current_deck_initialization",
    lambda: prepare_server_initialization(
        character, monsters, fight, 3, deck, action_id=1, rng=random.Random(1)
    ),
)
if initialized is not None:
    fight, init_packets = initialized
    while fight.current.id != 7:
        fight.end_server_turn(fight.current.id, fight.turn_id)
    print(
        "initialization_packets",
        len(init_packets),
        "states",
        [(e.reference, e.level) for e in fight.actors[7].state_ledger.entries],
        flush=True,
    )
    for spell in [5028, 5030, 5033, 5038]:
        variants = audit.target_candidates(
            audit.catalog()["spells"][str(spell)], 20, terrain, origin
        )
        legal_target = next((cell for name, cell in variants if name == "enemy"), None)
        if legal_target is None:
            print("No verified legal enemy target", spell, flush=True)
            continue
        cast_character, cast_monster, cast_fight = audit.fixture(
            11, 20, legal_target, terrain, origin
        )
        cast_fight, _ = prepare_server_initialization(
            cast_character,
            {-7: cast_monster},
            cast_fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(1),
        )
        while cast_fight.current.id != 7:
            cast_fight.end_server_turn(cast_fight.current.id, cast_fight.turn_id)
        print("legal_target", spell, legal_target, flush=True)
        measured(
            "spell_" + str(spell),
            lambda spell=spell: prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | spell, *legal_target),
                cast_character,
                {-7: cast_monster},
                cast_fight,
                3,
                deck,
                action_id=2,
                critical=False,
                rng=random.Random(1),
                line_of_sight=lambda a, b, p: authoritative_visible(
                    1134,
                    a,
                    b,
                    p,
                    blocking_footprints={
                        x.id: {x.position[:2]} for x in p.actors.values() if x.hp > 0
                    },
                ),
            ),
        )
for i in range(3):
    measured(
        "warm_factory_" + str(i),
        lambda: server_runtime(character, monsters, deck, action_id=2, critical=False),
    )
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
suite = unittest.defaultTestLoader.discover(
    str(Path(__file__).resolve().parents[1] / "tests"),
    pattern="test_combat_spell_transaction.py",
)
result = unittest.TextTestRunner(verbosity=1).run(suite)
report = {
    "rows": rows,
    "sources_stable": sources == audit.init.source_hashes(),
    "regression_tests": result.testsRun,
    "regression_success": result.wasSuccessful(),
}
Path("docs/reports/combat-runtime-performance.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print("FINAL", json.dumps(report), flush=True)
raise SystemExit(0 if result.wasSuccessful() else 1)
