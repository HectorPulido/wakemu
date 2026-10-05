"""Offline normal Carga through production Ready/cast on native terrain."""
from pathlib import Path
import sys, json, struct, random

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import audit_active_spells as audit
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.fight_checkpoint_store import snapshot

before_hash = audit.init.source_hashes()
geometry = audit.map_geometry(1134)
origin = (-8, -7, -1)
enemy = (-11, -7, -1)
terrain = audit.bounded_arena(geometry, origin, [enemy], radius=12)
rows = []
for level in (17, 200):
    char, npc, base = audit.fixture(8, level, enemy, terrain, origin)
    deck = audit.encode_deck([4783])
    rng = random.Random(0)
    source, packets = prepare_server_initialization(
        char, {-7: npc}, base, 3, deck, action_id=1, rng=rng, fight_start=True
    )
    while source.current.id != 7:
        source.end_server_turn(source.current.id, source.turn_id)
    original = snapshot(source)

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

    transaction = prepare_server_spell(
        struct.pack(">qqiih", 7, (7 << 32) | 4783, *enemy),
        char,
        {-7: npc},
        source,
        3,
        deck,
        action_id=2,
        line_of_sight=los,
        critical=False,
        rng=rng,
    )
    events = transaction.fight.events[len(source.events) :]
    movement = [
        e
        for e in events
        if e["kind"] == "effect_displacement" and e["effect_class"] == 305
    ]
    assert (
        movement and transaction.fight.actors[7].position != source.actors[7].position
    )
    assert transaction.fight.actors[-7].hp < source.actors[-7].hp
    assert snapshot(source) == original
    rows.append(
        dict(
            level=level,
            critical=False,
            origin=origin,
            target=enemy,
            caster_after=transaction.fight.actors[7].position,
            hp_before=source.actors[-7].hp,
            hp_after=transaction.fight.actors[-7].hp,
            events=events,
            rollback_preserved=True,
        )
    )
report = dict(rows=rows, sources_stable=before_hash == audit.init.source_hashes())
assert report["sources_stable"]
Path("docs/reports/combat-inventory/carga4783-normal-distant-current.json").write_text(
    json.dumps(report, indent=2) + "\n"
)
print(
    "Normal Carga4783 distant: 2PASS; 305 movement, damage, rollback and source stability"
)
