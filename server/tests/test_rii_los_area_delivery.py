"""Native LOS area wire identities stay synchronized with each obstacle generation."""

import random
import struct
import unittest
from types import SimpleNamespace

import test_combat_spell_transaction as fixture
from wakfu_server.combat_actor_snapshot import build_player_snapshot, build_npc_snapshot
from wakfu_server.combat_state import Fight, Actor
from wakfu_server.combat_terrain import local_arena, published_geometry
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
    move_registered_actor,
)
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_turn_end,
    prepare_server_turn_start,
    prepare_server_spell,
)
from wakfu_server.combat_casting_los import native_casting_los
from wakfu_server.spells import encode_deck
from wakfu_server.wire import proto_fields


def fields(raw):
    return {tag >> 3: value for tag, value in proto_fields(raw)}


def signed(value):
    return value - (1 << 64) if value >= (1 << 63) else value


class AreaDeliveryTests(unittest.TestCase):
    def test_all_los_generations_deliver_exact_registered_uid_cells(self):
        wire_areas = {}

        def parity(fight, packets):
            # Simulate the native Qs creation/removal registry from the packets,
            # independently of the server's registered native effect-area rows.
            for opcode, body in packets:
                raw = None
                if (
                    opcode == 12613
                    and len(body) >= 19
                    and struct.unpack_from(">i", body, 13)[0] == 315
                ):
                    raw = body[19:]
                elif (
                    opcode == 13497
                    and len(body) >= 18
                    and struct.unpack_from(">i", body, 12)[0] == 315
                ):
                    raw = body[18:]
                elif opcode == 13726:
                    wire_areas.pop(struct.unpack_from(">q", body, 12)[0], None)
                if raw is not None:
                    data = fields(raw)
                    if data.get(4) == 1808:
                        cell, extra = fields(data[5]), fields(data[8])
                        wire_areas[extra[21]] = tuple(
                            signed(cell.get(index, 0)) for index in (1, 2, 3)
                        )
            self.assertEqual(
                wire_areas,
                {
                    uid: tuple(row["cell"])
                    for uid, row in fight.native_effect_areas.items()
                    if row["reference"] == 1808
                },
            )

        c, m, prior = fixture.SpellTransactionTests().native_server_fixture(
            8, 6, target_ref=5466, target_level=1
        )
        c.update(map_id=1388, x=0, y=-10, z=0, instance_id=0)
        m["map_id"] = 1388
        old = prior.actors[7]
        owner = Actor(
            7,
            0,
            (0, -10, 0),
            old.hp,
            old.ap,
            old.mp,
            old.initiative,
            6,
            3,
            True,
            max_hp=old.max_hp,
        )
        cells = [(0, -13, 0)]
        actors = [owner]
        monsters = {}
        for idx, cell in enumerate(cells):
            old = prior.actors[-7]
            a = Actor(
                -7 - idx, 1, cell, old.hp, old.ap, old.mp, 5, 1, max_hp=old.max_hp
            )
            actors.append(a)
            monsters[a.id] = dict(m, id=a.id)
        arena = local_arena(
            1388,
            7,
            owner.position,
            cells,
            relocate_monsters=False,
            ordinary_npc_placement=True,
            allowed_cells={
                p
                for p in published_geometry(1388).cells
                if -5 <= p[0] <= 5 and -18 <= p[1] <= -8 and p[2] == 0
            },
        )
        f = Fight(
            78,
            actors,
            arena["validated_cells"],
            {0: {owner.position}, 1: set(cells)},
            arena["valid_edges"],
        )
        f.native_qi_snapshot = {
            k: arena[k] for k in ("x", "y", "width", "height", "cell_masks")
        }
        f.native_qi_surface_provenance = dict(arena["native_qi_surface_provenance"])
        freeze_terrain(f)
        initialize_global_pv_collections(f, tuple(a.id for a in actors))
        snapshots = {
            7: build_player_snapshot(
                c, owner, wp_current=6, wp_maximum=6, running_effects=()
            )
        }
        for a in actors[1:]:
            snapshots[a.id] = build_npc_snapshot(
                monsters[a.id], a, wp_current=0, wp_maximum=0, running_effects=()
            )
        install_fresh_actor_slots(
            f,
            prepare_fresh_actor_slots(
                f, physical_radii={i: s.physical_radius for i, s in snapshots.items()}
            ),
        )
        f.ready(3)
        for a in actors:
            snapshots[a.id].install(a)
        f.native_effect_uid_next = 1
        f.native_obstacle_cells = frozenset()
        contract = {"owner": 7, "hits": 0}
        contract.update(target=-7, native_los_areas=True)
        f.rii_los_lesson_contract = contract
        result, packets = prepare_server_initialization(
            c,
            monsters,
            f,
            3,
            encode_deck([]),
            action_id=1,
            rng=random.Random(1),
            fight_start=True,
        )
        f = result
        parity(f, packets)

        class Authority:
            def __call__(self, fight, actor):
                return SimpleNamespace(native_instance_id=1388)

            def properties(self, fight, actor):
                return actor.native_fight_properties

        authority = Authority()
        f, packets = prepare_server_turn_start(
            c,
            monsters,
            f,
            encode_deck([]),
            actor_id=7,
            action_id=2,
            rng=random.Random(1),
        )
        parity(f, packets)
        self.assertEqual(len(wire_areas), 16)
        # Idle turns use the same8003 retirement program with the owner as
        # transmitted target. They must not keep one obstacle per overlapping
        # coordinate while the remaining generation expires by its timers.
        for boundary in range(12):
            previous = set(wire_areas)
            f, packets = prepare_server_turn_end(
                c,
                monsters,
                f,
                encode_deck([]),
                actor_id=f.current.id,
                action_id=100 + boundary * 2,
                rng=random.Random(1),
            )
            parity(f, packets)
            f._advance()
            f, packets = prepare_server_turn_start(
                c,
                monsters,
                f,
                encode_deck([]),
                actor_id=f.current.id,
                action_id=101 + boundary * 2,
                rng=random.Random(1),
            )
            parity(f, packets)
            self.assertEqual(len(wire_areas), 16)
            if f.current.id == 7:
                self.assertFalse(previous.intersection(wire_areas))
        for step in range(4):
            target = f.actors[-7]
            previous = set(wire_areas)
            for cell in sorted(f.walkable):
                if (
                    not 4
                    <= sum(abs(cell[i] - target.position[i]) for i in (0, 1))
                    <= 16
                ):
                    continue
                move_registered_actor(f, f.actors[7], cell)
                if native_casting_los(f, authority, 7, target.position, target):
                    break
            else:
                self.fail("Native obstacle generation has no legal firing cell")
            cast = prepare_server_spell(
                struct.pack(">qqiih", 7, 7968, *target.position),
                c,
                monsters,
                f,
                3,
                encode_deck([]),
                action_id=step + 3,
                line_of_sight=lambda *_: True,
                critical=False,
                rng=random.Random(step + 1),
            )
            f = cast.fight
            parity(f, cast.packets)
            self.assertEqual(f.actors[-7].hp, 75 - step * 25)
            if step < 3:
                self.assertFalse(previous.intersection(wire_areas))
            self.assertEqual(len(wire_areas), 15)
        self.assertEqual((f.phase, f.winner), ("finished", 0))
