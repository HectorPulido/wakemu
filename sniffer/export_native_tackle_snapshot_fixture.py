"""Export offline player/NPC movement snapshots for the original JVM oracle.

Run from the repository root with PYTHONPATH=server and the existing local
read-only native-catalog connection environment. This creates fixture files
only; it does not connect a gameplay client or mutate game data.
"""

import argparse
from pathlib import Path
import json
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_actor import actual_actor_stats, actual_monster_actor_stats
from wakfu_server.combat_wire import actor_state
from wakfu_server.combat_actor_snapshot import native_characteristic_definitions
from wakfu_server.combat_tackle_movement import movement_tackle_cost
from wakfu_server.combat_movement_runtime import movement_stats_snapshots
from wakfu_server.combat_wire import decode_actor_state
from wakfu_server.combat_runtime_adapter import NativeActorAuthority
from wakfu_server.combat_tackle_loss_messages import tackle_loss_messages


class Authority:
    """Explicit fixture affiliation/status facts, without live ownership claims."""

    def __call__(self, fight, actor):
        return NativeActorAuthority(
            targeting=dict(baF=True, baG=False, baK=False, dpu_id=actor.id),
            is_player=actor.controlled,
            deck_spell_ids=frozenset(),
            excluded_deck_spell_ids=frozenset(),
            is_carried=False,
            breed_id=1,
            summon_count=0,
            summon_counts_by_breed={},
            occupant_blocks=True,
        )

    def properties(self, fight, actor):
        return frozenset()


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument(
    "--output", type=Path, default=Path(".runtime/tackle-wire-audit/fixture")
)
out = parser.parse_args().output
out.mkdir(parents=True, exist_ok=True)
rows = native_characteristic_definitions()


def fixture(mover):
    p = Actor(84, 0, (1, 0, 0), 100, 6, 5, 0, 29, 54, True)
    n = Actor(-1125899928606083, 1, (0, 0, 0), 100, 6, 3, 0, 8)
    for a, lock, dodge, direction, ai in ((p, 74, -20, 5, False), (n, 6, 16, 1, True)):
        values = {1: 100, 2: a.ap, 3: a.mp, 4: 0, 7: lock, 8: dodge, 35: 0}
        maxima = {
            k: (
                100
                if k == 1
                else a.max_ap
                if k == 2
                else a.max_mp
                if k == 3
                else 0
                if k == 4
                else rows[k]["hard_maximum"]
            )
            for k in values
        }
        minima = {k: rows[k]["hard_minimum"] for k in values}
        a.effect_stats = dict(values)
        a.effect_minima = dict(minima)
        a.effect_maxima = dict(maxima)
        a.effect_base_minima = dict(minima)
        a.effect_base_maxima = dict(maxima)
        a.effect_percentages = {k: 0 for k in values}
        a.effect_frozen = frozenset()
        a.physical_radius = 0
        a.direction = direction
        a.native_fight_property_counts = {}
        a.native_world_property_counts = {}
        a.native_controlled_by_ai = ai
    cells = {(x, y, 0) for x in range(-2, 4) for y in range(-2, 4)}
    f = Fight(671, [p, n], cells, {0: {p.position}, 1: {n.position}})
    f.native_rail_movement_authority = Authority()
    f.phase = "active"
    f.order = [p.id, n.id] if mover == "player" else [n.id, p.id]
    f.turn_index = 0
    f.turn_id = 1
    f.current.turn_count = 1
    return f, p, n


def snapshot(f, a):
    if a.controlled:
        char = dict(
            id=a.id,
            account_id=54,
            level=29,
            breed=11,
            hp=a.hp,
            max_hp=a.max_hp,
            map_id=902,
            instance_id=0,
        )
        blob = actual_actor_stats(char, a, f.id, wp_current=0, wp_maximum=0)
    else:
        monster = dict(
            id=a.id,
            ref=6,
            team=1,
            level=8,
            hp=a.hp,
            max_hp=a.max_hp,
            map_id=902,
            instance_id=0,
        )
        blob = actual_monster_actor_stats(monster, a, f.id, wp_current=0, wp_maximum=0)
    return actor_state(12873, f.id, a.id, blob)


receipts = []
for kind in ("player", "npc"):
    f, p, n = fixture(kind)
    a = p if kind == "player" else n
    (out / (kind + "-before.bin")).write_bytes(snapshot(f, a))
    path = [(1, 1, 0)] if kind == "player" else [(0, 1, 0)]
    tax = movement_tackle_cost(f, a, path)
    (out / (kind + "-cost.txt")).write_text(",".join(map(str, tax)))
    event = (
        f.move(a.owner_id, a.id, path)
        if kind == "player"
        else f.server_move(a.id, path)
    )
    for index, (opcode, packet) in enumerate(
        tackle_loss_messages(f.id, 1, a.id, event)
    ):
        assert opcode == 12613
        (out / (kind + f"-loss-{index}.bin")).write_bytes(packet)
    full_after = decode_actor_state(12873, snapshot(f, a))["state"]
    full_before = decode_actor_state(
        12873, (out / (kind + "-before.bin")).read_bytes()
    )["state"]
    projected = movement_stats_snapshots(full_after, full_before, actor=a)
    assert projected[0][0] == 40
    (out / (kind + "-after.bin")).write_bytes(
        actor_state(12873, f.id, a.id, projected[0])
    )
    (out / (kind + "-after-properties.bin")).write_bytes(
        actor_state(12873, f.id, a.id, projected[1])
    )
    receipts.append(
        dict(
            kind=kind,
            event=event,
            AP=a.ap,
            MP=a.mp,
            lock=a.effect_stats[7],
            dodge=a.effect_stats[8],
        )
    )
print(json.dumps(receipts, indent=2))
