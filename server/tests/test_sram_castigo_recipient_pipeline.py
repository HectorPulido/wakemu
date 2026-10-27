"""Paid native Castigo retains each chosen cross-ring recipient through commit."""
from collections import Counter
import random
import struct
import unittest

import test_combat_spell_transaction as transaction_fixtures
from wakfu_server.combat_actor_snapshot import build_npc_snapshot, build_player_snapshot
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_qi_fight import (
    prepare_fresh_actor_slots,
    install_fresh_actor_slots,
)
from wakfu_server.combat_runtime_messages import RuntimeMessages
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    prepare_server_spell,
)
from wakfu_server.combat_spell_commit import commit_spell_transaction
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_terrain import local_arena
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck


class SramCastigoRecipientPipelineTests(unittest.TestCase):
    @staticmethod
    def weak_point(fight):
        return sum(
            row.level
            for row in fight.actors[7].state_ledger.entries
            if row.reference == 3114
        )

    def fixture(self, target_position=None, *, ring=False):
        (
            character,
            monster,
            fight,
        ) = transaction_fixtures.SpellTransactionTests().native_server_fixture(
            4,
            30,
            full_health=True,
            native_qi=True,
            target_ref=4168,
            target_level=190,
            target_distance=1,
            target_position=target_position,
            variation_seed=17,
        )
        characters, monsters = {7: character}, {-7: monster}
        if ring:
            # Build one fresh official QI population before any initialization;
            # copying an already installed fighter would duplicate its authority.
            center = fight.actors[7].position
            positions = {
                identity: (center[0] + dx, center[1] + dy, center[2])
                for identity, dx, dy in (
                    (-7, 1, 0),
                    (-8, 0, 1),
                    (-9, -1, 0),
                    (6, 0, -1),
                    (-10, 1, 1),
                )
            }
            terrain = local_arena(
                1134,
                7,
                center,
                tuple(positions.values()),
                relocate_monsters=False,
                variation_seed=17,
            )
            pc, npc = fight.actors[7], fight.actors[-7]
            actors = [
                Actor(
                    7,
                    0,
                    center,
                    pc.hp,
                    pc.ap,
                    pc.mp,
                    pc.initiative,
                    30,
                    3,
                    True,
                    max_hp=pc.max_hp,
                )
            ]
            build_player_snapshot(
                character, actors[0], wp_current=6, wp_maximum=6, running_effects=()
            ).install(actors[0])
            for identity, position in positions.items():
                if identity == 6:
                    ally = dict(character, id=6)
                    characters[6] = ally
                    actor = Actor(
                        6,
                        0,
                        position,
                        pc.hp,
                        pc.ap,
                        pc.mp,
                        pc.initiative,
                        30,
                        3,
                        True,
                        max_hp=pc.max_hp,
                    )
                    build_player_snapshot(
                        ally, actor, wp_current=6, wp_maximum=6, running_effects=()
                    ).install(actor)
                else:
                    source = dict(monster, id=identity)
                    monsters[identity] = source
                    actor = Actor(
                        identity,
                        1,
                        position,
                        npc.hp,
                        npc.ap,
                        npc.mp,
                        npc.initiative,
                        npc.effective_level,
                        max_hp=npc.max_hp,
                    )
                    build_npc_snapshot(
                        source, actor, wp_current=0, wp_maximum=0, running_effects=()
                    ).install(actor)
                actors.append(actor)
            fight = Fight(
                78,
                actors,
                terrain["validated_cells"],
                {
                    0: {a.position for a in actors if a.controlled},
                    1: {a.position for a in actors if not a.controlled},
                },
                terrain["valid_edges"],
            )
            fight.native_qi_snapshot = {
                key: terrain[key] for key in ("x", "y", "width", "height", "cell_masks")
            }
            fight.native_qi_surface_provenance = dict(
                terrain["native_qi_surface_provenance"]
            )
            freeze_terrain(fight)
            initialize_global_pv_collections(fight, tuple(fight.actors))
            install_fresh_actor_slots(
                fight,
                prepare_fresh_actor_slots(
                    fight, physical_radii={a.id: a.physical_radius for a in actors}
                ),
            )
            fight.native_effect_uid_next = 1
            fight.native_obstacle_cells = frozenset()
            fight.ready(3)
        deck = encode_deck([4579, 4589])
        for index, source in enumerate(characters.values()):
            fight, _ = prepare_server_initialization(
                source,
                monsters,
                fight,
                3,
                deck,
                action_id=1,
                rng=random.Random(17),
                fight_start=index == len(characters) - 1,
                player_characters=characters,
                deck_blobs={identity: deck for identity in characters},
            )
        self.assertTrue(fight.native_start_event_delivered)
        self.assertEqual(fight.current.id, 7)
        return characters, monsters, RuntimeMessages(fight), deck

    def cast(self, fixture, spell=4589, *, critical=False):
        from wakfu_server.combat_actor import (
            actual_actor_stats,
            actual_monster_actor_stats,
        )

        characters, monsters, runtime, deck = fixture
        original = snapshot(runtime.fight)
        target = runtime.fight.actors[7 if spell == 4589 else -7].position

        def los(origin, destination, current):
            return authoritative_visible(
                1134,
                origin,
                destination,
                current,
                blocking_footprints={
                    a.id: footprint(a.position, a.physical_radius)
                    for a in current.actors.values()
                    if a.hp > 0
                },
            )

        tx = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | spell, *target),
            characters[7],
            monsters,
            runtime.fight,
            3,
            deck,
            action_id=runtime.action_id + 1,
            line_of_sight=los,
            critical=critical,
            rng=random.Random(17),
            player_characters=characters,
            deck_blobs={identity: deck for identity in characters},
        )
        self.assertEqual(snapshot(runtime.fight), original)

        def stats(actor, current):
            encoder = (
                actual_actor_stats if actor.controlled else actual_monster_actor_stats
            )
            source = (
                characters[actor.id]
                if actor.controlled
                else dict(monsters[actor.id], level=actor.effective_level)
            )
            return encoder(
                source,
                actor,
                current.id,
                wp_current=actor.effect_stats[4],
                wp_maximum=actor.effect_maxima[4],
                fight=current,
            )

        packets = commit_spell_transaction(runtime, tx, stats_serializer=stats)
        self.assertTrue(packets)
        return tx, packets

    @staticmethod
    def damaged_recipients(packets):
        counts = Counter()
        for opcode, body in packets:
            if opcode != 12613 or len(body) < 19:
                continue
            _, _, _, _, family, size = struct.unpack_from(">iiiBih", body)
            if family not in (1, 2, 3, 4, 5):
                continue
            fields = _identity_fields(body[19 : 19 + size])
            target = fields[7]
            if target >= 1 << 63:
                target -= 1 << 64
            counts[target] += 1
        return counts

    @staticmethod
    def damage_references(packets):
        return [
            _identity_fields(body[19:])[3]
            for opcode, body in packets
            if opcode == 12613
            and len(body) >= 19
            and struct.unpack_from(">i", body, 13)[0] in (1, 2, 3, 4, 5)
        ]

    def test_paid_cast_excludes_center_for_all_cardinal_positions_and_critical(self):
        positions = ((-7, -7, -1), (-8, -6, -1), (-9, -7, -1), (-8, -8, -1))
        cases = [(position, False) for position in positions] + [(positions[0], True)]
        for position, critical in cases:
            with self.subTest(position=position, critical=critical):
                fixture = self.fixture(position)
                runtime = fixture[2]
                before = {
                    identity: actor.hp
                    for identity, actor in runtime.fight.actors.items()
                }
                ap = runtime.fight.actors[7].ap
                tx, packets = self.cast(fixture, critical=critical)
                self.assertEqual(tx.plan["costs"]["ap"], 4)
                self.assertEqual(runtime.fight.actors[7].ap, ap - 4)
                self.assertEqual(runtime.fight.actors[7].hp, before[7])
                self.assertLess(runtime.fight.actors[-7].hp, before[-7])
                self.assertEqual(self.damaged_recipients(packets), Counter({-7: 1}))
                self.assertEqual(
                    self.damage_references(packets), [409963 if critical else 120562]
                )
                self.assertEqual(self.weak_point(runtime.fight), 70)

    def test_each_cross_neighbor_is_hurt_once_including_ally_but_center_and_corner_are_not(
        self,
    ):
        for critical in (False, True):
            with self.subTest(critical=critical):
                fixture = self.fixture(ring=True)
                runtime = fixture[2]
                before = {
                    identity: actor.hp
                    for identity, actor in runtime.fight.actors.items()
                }
                tx, packets = self.cast(fixture, critical=critical)
                self.assertEqual(tx.plan["costs"]["ap"], 4)
                for identity in (-7, -8, -9, 6):
                    self.assertLess(runtime.fight.actors[identity].hp, before[identity])
                for identity in (7, -10):
                    self.assertEqual(
                        runtime.fight.actors[identity].hp, before[identity]
                    )
                self.assertEqual(
                    self.damaged_recipients(packets),
                    Counter({-7: 1, -8: 1, -9: 1, 6: 1}),
                )
                self.assertEqual(self.weak_point(runtime.fight), 70)

    def test_paid_estafa_then_castigo_uses_one_real_six_ap_turn(self):
        fixture = self.fixture()
        runtime = fixture[2]
        self.assertEqual(runtime.fight.actors[7].ap, 6)
        self.assertEqual(self.weak_point(runtime.fight), 50)
        first, _ = self.cast(fixture, 4579)
        self.assertEqual(first.plan["costs"]["ap"], 2)
        # Native effects return one AP after the genuine two-AP payment.
        self.assertEqual(runtime.fight.actors[7].ap, 5)
        self.assertLess(self.weak_point(runtime.fight), 50)
        self.assertIn(
            9131,
            {row.reference for row in runtime.fight.actors[7].state_ledger.entries},
        )
        before = {
            identity: actor.hp for identity, actor in runtime.fight.actors.items()
        }
        weak_before = self.weak_point(runtime.fight)
        second, packets = self.cast(fixture)
        self.assertEqual(second.plan["costs"]["ap"], 4)
        self.assertEqual(runtime.fight.actors[7].ap, 1)
        self.assertEqual(runtime.fight.actors[7].hp, before[7])
        self.assertLess(runtime.fight.actors[-7].hp, before[-7])
        # The natural9131 branch has two distinct native damage leaves;
        # each applies once to the chosen enemy, never to the center caster.
        self.assertEqual(self.damaged_recipients(packets), Counter({-7: 2}))
        self.assertEqual(self.weak_point(runtime.fight), weak_before + 20)
        self.assertEqual(self.damage_references(packets), [409962, 411469])
