"""Real class AOE casts retain each native recipient through paid commit."""
from collections import Counter
from copy import deepcopy
import json
import os
import random
import struct
import unittest

import test_combat_spell_transaction as transaction_fixtures
from wakfu_server.combat_actor_snapshot import build_npc_snapshot
from wakfu_server.combat_effect_removal import _identity_fields
from wakfu_server.combat_geometry_snapshot import freeze_terrain
from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_los import authoritative_visible
from wakfu_server.combat_obstacle_condition import footprint
from wakfu_server.combat_qi_fight import (
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
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


# Coordinates are relative to the caster on real map1134. Every target has
# its complete natural NPC4168 level190 profile, rather than edited HP.
CASES = (
    dict(
        breed=16,
        spell=6909,
        name="Espuma de Mar",
        shape="t inv-barre:1-pied:0",
        target=(1, 0),
        occupants=((1, 0), (1, 1), (1, -1)),
        costs=(3, 0, 0),
        leaves=(343276, 343760),
    ),
    dict(
        breed=14,
        spell=7067,
        name="Hendidura",
        shape="t-1-1",
        target=(1, 0),
        occupants=((1, 0), (2, 0), (2, 1)),
        costs=(3, 0, 0),
        leaves=(307478, 307481),
    ),
    dict(
        breed=3,
        spell=2013,
        name="Pala Sismica",
        shape="t-0-2",
        target=(1, 0),
        occupants=((1, 0), (2, 0), (3, 0)),
        costs=(5, 0, 1),
        leaves=(36828, 255073),
    ),
    dict(
        breed=10,
        spell=937,
        name="Zarzas Multiples",
        shape="circle-2",
        target=(3, 0),
        occupants=((3, 0), (3, 1), (4, 0)),
        costs=(5, 0, 1),
        leaves=(6874, 91091),
    ),
    dict(
        breed=12,
        spell=4705,
        name="Frasco Explosivo",
        shape="cross-h1b1-g1d1",
        target=(3, 0),
        occupants=((3, 0), (3, 1), (4, 0)),
        costs=(4, 0, 0),
        leaves=(417394, 417399),
    ),
)


class CrossClassAOEPaidRecipientTests(unittest.TestCase):
    def fixture(self, case):
        origin = (-8, -7, -1)

        def cell(offset):
            return origin[0] + offset[0], origin[1] + offset[1], origin[2]

        (
            character,
            monster,
            template,
        ) = transaction_fixtures.SpellTransactionTests().native_server_fixture(
            case["breed"],
            30,
            full_health=True,
            native_qi=True,
            target_ref=4168,
            target_level=190,
            target_position=cell(case["occupants"][0]),
            variation_seed=17,
        )
        positions = {
            identity: cell(offset)
            for identity, offset in zip((-7, -8, -9), case["occupants"])
        }
        target_cell = cell(case["target"])
        positions[-10] = next(
            p
            for p in sorted(template.walkable)
            if p[2] == origin[2]
            and p[0] < origin[0]
            and abs(p[0] - target_cell[0]) + abs(p[1] - target_cell[1]) >= 6
        )
        terrain = local_arena(
            1134,
            7,
            origin,
            tuple(positions.values()),
            relocate_monsters=False,
            variation_seed=17,
        )
        caster = template.actors[7]
        caster.turn_count = 0
        actors = [caster]
        monsters = {}
        native_npc = template.actors[-7]
        for identity, position in positions.items():
            source = dict(monster, id=identity, level=190)
            monsters[identity] = source
            actor = Actor(
                identity,
                1,
                position,
                native_npc.hp,
                native_npc.ap,
                native_npc.mp,
                native_npc.initiative,
                190,
                max_hp=native_npc.max_hp,
            )
            actor.direction = 3
            build_npc_snapshot(
                source, actor, wp_current=0, wp_maximum=0, running_effects=()
            ).install(actor)
            actors.append(actor)
        fight = Fight(
            78018,
            actors,
            terrain["validated_cells"],
            {0: {origin}, 1: set(positions.values())},
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
        deck = encode_deck([case["spell"]])
        fight, initialization = prepare_server_initialization(
            character,
            monsters,
            fight,
            3,
            deck,
            action_id=1,
            rng=random.Random(17),
            fight_start=True,
            player_characters={7: character},
            deck_blobs={7: deck},
        )
        self.assertTrue(fight.native_start_event_delivered)
        self.assertEqual(fight.current.id, 7)
        return character, monsters, fight, deck, cell(case["target"])

    @staticmethod
    def damage_records(packets):
        records = []
        for opcode, body in packets:
            if opcode != 12613 or len(body) < 19:
                continue
            family, size = struct.unpack_from(">ih", body, 13)
            if family not in (1, 2, 3, 4, 5):
                continue
            fields = _identity_fields(body[19 : 19 + size])
            target = fields[7]
            if target >= 1 << 63:
                target -= 1 << 64
            records.append((fields[3], target))
        return records

    def test_paid_native_multitarget_normal_and_critical_recipient_contracts(self):
        proofs = []
        selected = (
            set(map(int, os.environ.get("WAKFU_QA_AOE_SPELLS", "").split(",")))
            if os.environ.get("WAKFU_QA_AOE_SPELLS")
            else None
        )
        for case in CASES:
            if selected is not None and case["spell"] not in selected:
                continue
            fixture = None
            with self.subTest(spell=case["spell"], preparation=True):
                fixture = self.fixture(case)
            if fixture is None:
                continue
            for critical in (False, True):
                with self.subTest(spell=case["spell"], critical=critical):
                    character, monsters, baseline, deck, target = deepcopy(fixture)
                    runtime = RuntimeMessages(baseline)
                    before = snapshot(baseline)
                    ap, mp, wp = (
                        baseline.actors[7].ap,
                        baseline.actors[7].mp,
                        baseline.actors[7].effect_stats[4],
                    )
                    hp = {
                        identity: actor.hp
                        for identity, actor in baseline.actors.items()
                    }

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
                        struct.pack(">qqiih", 7, (7 << 32) | case["spell"], *target),
                        character,
                        monsters,
                        baseline,
                        3,
                        deck,
                        action_id=1,
                        line_of_sight=los,
                        critical=critical,
                        rng=random.Random(17),
                        player_characters={7: character},
                        deck_blobs={7: deck},
                    )
                    self.assertEqual(snapshot(baseline), before)
                    from wakfu_server.combat_actor import (
                        actual_actor_stats,
                        actual_monster_actor_stats,
                    )

                    def stats(actor, current):
                        if actor.id in getattr(
                            current, "native_summon_registrations", {}
                        ):
                            from wakfu_server.combat_summon_stats import (
                                registered_summon_stats,
                            )

                            return registered_summon_stats(actor, current, 1134)
                        encoder = (
                            actual_actor_stats
                            if actor.controlled
                            else actual_monster_actor_stats
                        )
                        source = character if actor.controlled else monsters[actor.id]
                        return encoder(
                            source,
                            actor,
                            current.id,
                            wp_current=actor.effect_stats[4],
                            wp_maximum=actor.effect_maxima[4],
                            fight=current,
                        )

                    packets = commit_spell_transaction(
                        runtime, tx, stats_serializer=stats
                    )
                    self.assertEqual(
                        tuple(tx.plan["costs"][k] for k in ("ap", "mp", "wp")),
                        case["costs"],
                    )
                    records = self.damage_records(packets)
                    wanted_leaf = case["leaves"][int(critical)]
                    self.assertEqual(
                        Counter(records),
                        Counter(
                            {(wanted_leaf, identity): 1 for identity in (-7, -8, -9)}
                        ),
                    )
                    for identity in (-7, -8, -9):
                        self.assertLess(runtime.fight.actors[identity].hp, hp[identity])
                    # Every selected geometry excludes this caster placement;
                    # do not generalize this to spells with native self-damage.
                    self.assertEqual(runtime.fight.actors[7].hp, hp[7])
                    self.assertEqual(runtime.fight.actors[-10].hp, hp[-10])
                    self.assertEqual(runtime.fight.actors[7].ap, ap - case["costs"][0])
                    self.assertEqual(runtime.fight.actors[7].mp, mp - case["costs"][1])
                    self.assertEqual(
                        runtime.fight.actors[7].effect_stats[4], wp - case["costs"][2]
                    )
                    proofs.append(
                        dict(
                            spell=case["spell"],
                            breed=case["breed"],
                            geometry=case["shape"],
                            critical=critical,
                            costs=case["costs"],
                            damage_records=records,
                            recipient_hp_before={str(i): hp[i] for i in (-7, -8, -9)},
                            recipient_hp_after={
                                str(i): runtime.fight.actors[i].hp for i in (-7, -8, -9)
                            },
                            effects_after={
                                str(i): [r.reference for r in a.state_ledger.entries]
                                for i, a in runtime.fight.actors.items()
                            },
                        )
                    )
        self.assertTrue(proofs)
        self.proof = proofs
        receipt = os.environ.get("WAKFU_QA_AOE_RECEIPT")
        if receipt:
            with open(receipt, "w") as stream:
                json.dump(
                    dict(
                        scope="Real native paid AOE sample; not all class spells",
                        cases=proofs,
                    ),
                    stream,
                    indent=2,
                )
