"""Offline immutable-catalogue and ordinary cast timings; no session/DB writes."""
import argparse, cProfile, json, pstats, random, struct, time
from types import SimpleNamespace
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
import audit_active_spells as audit
from wakfu_server.combat_server_spell import (
    prepare_server_spell,
    prepare_server_initialization,
)
from wakfu_server.spells import encode_deck
from wakfu_server.combat_los import authoritative_visible

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--radius", type=int, default=12)
args = parser.parse_args()
geometry = audit.map_geometry(1134)
origin = (-8, -7, -1)
target = (-9, -7, -1)
terrain = audit.bounded_arena(geometry, origin, [target], radius=args.radius)
character, monster, fight = audit.fixture(11, 20, target, terrain, origin)
deck = encode_deck([5038], [], -1)
profile = cProfile.Profile()
profile.enable()
start = time.perf_counter()
fight, _ = prepare_server_initialization(
    character, {-7: monster}, fight, 3, deck, action_id=1, rng=random.Random(1)
)
print("initialization_seconds", time.perf_counter() - start, flush=True)
while fight.current.id != 7:
    fight.end_server_turn(fight.current.id, fight.turn_id)
for i in range(3):
    start = time.perf_counter()
    try:
        result = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 5038, *target),
            character,
            {-7: monster},
            fight,
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
        )
        print(
            "cast",
            i,
            "seconds",
            time.perf_counter() - start,
            "packets",
            len(result.packets),
            flush=True,
        )
        # Exercise the same serialization and source checks as the session,
        # without sending packets or mutating the authoritative fixture.
        runtime = SimpleNamespace(
            fight=fight,
            action_id=1,
            awaiting_ack=None,
            pending=[],
            _flush=lambda: (13420, b""),
        )

        def serialize(actor, state):
            options = dict(
                wp_current=actor.effect_stats[4], wp_maximum=actor.effect_maxima[4]
            )
            if actor.controlled:
                return actual_actor_stats(character, actor, state.id, **options)
            return actual_monster_actor_stats(monster, actor, state.id, **options)

        commit_started = time.perf_counter()
        commit_spell_transaction(
            runtime,
            result,
            stats_serializer=serialize,
            diagnostic=lambda **row: print("commit_stage", row, flush=True),
        )
        print("commit_seconds", time.perf_counter() - commit_started, flush=True)
    except ValueError as error:
        print(
            "rejection", str(error), "seconds", time.perf_counter() - start, flush=True
        )
profile.disable()
pstats.Stats(profile).sort_stats("cumtime").print_stats(25)
