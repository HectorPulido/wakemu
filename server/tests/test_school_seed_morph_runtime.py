"""Candidate profile proof through native state, morph, and normal cast runtime."""
import json
from pathlib import Path
import struct
import unittest
from unittest.mock import patch

import wakfu_server.combat_morph_handler as morph_handler


ROOT = Path(__file__).parents[1]
PROFILE_FILE = (
    ROOT.parent / ".runtime/quest-archetypes/school-player-morph-profiles.json"
)


class SchoolSeedMorphRuntimeTests(unittest.TestCase):
    def test_original_seed_state_grants_candidate_book_and_native_cast_rules_apply(
        self,
    ):
        from native_recorded_instance_fixture import original_bootstrap_publication
        from jondo_native_support_probe import build_fixture
        from wakfu_server.combat_qi_fight import move_registered_actor
        from wakfu_server.combat_los import authoritative_visible
        from wakfu_server.combat_obstacle_condition import footprint
        from wakfu_server.combat_server_spell import prepare_server_spell
        from wakfu_server.combat_spell_commit import commit_spell_transaction
        from wakfu_server.combat_native_spell_casting import native_casting_table

        source = json.loads(PROFILE_FILE.read_text())
        profile = source["profiles"]["3907"]
        self.assertEqual(source["native_book_checks"], 5)
        self.assertEqual(
            profile["abilities"],
            [
                dict(
                    reference=5599,
                    casting_uid=5599,
                    maximum_level=200,
                    override_level=-1,
                )
            ],
        )
        profiles = {"3907": profile}

        # Candidate-only injection: the production profile catalogue stays
        # untouched, while every original state/effect/cast handler is active.
        with patch.object(
            morph_handler, "native_morph_profiles", return_value=profiles
        ), original_bootstrap_publication():
            case = build_fixture(3907, 1, allies=((3908, 1, (-5, -7, -1)),))

        fight = case.fight
        player, seed = fight.actors[7], fight.actors[-7]
        self.assertIn(4071, {row.reference for row in seed.state_ledger.entries})
        self.assertIn(4072, {row.reference for row in player.state_ledger.entries})
        morph = fight.native_morph_spellbooks[7]
        self.assertEqual(morph["profile_id"], 3907)
        self.assertEqual(morph["levels"], {5599: 1})
        self.assertEqual(morph["own_level"], False)
        self.assertEqual(morph["removed_raw_uids"], set())

        record, index = native_casting_table(5599, 1)
        self.assertEqual(record["costs"][index], [0, 0, 0])
        self.assertEqual(record["levels"][index], [1, 1, [173894, 173895]])
        self.assertTrue(record["line_of_sight"])
        self.assertFalse(record["allow_self"])
        self.assertEqual(
            record["cast_criterion_raw"],
            'IsEnnemy() and IsBreedId("target", 3907)',
        )

        # Place the two native NPCs in distinct adjacent, legal cells for this
        # isolated cast fixture; position registration still goes through QI.
        occupied = {tuple(actor.position) for actor in fight.actors.values()}
        adjacent = sorted(
            cell
            for cell in fight.walkable
            if cell[2] == player.position[2]
            and abs(cell[0] - player.position[0]) + abs(cell[1] - player.position[1])
            == 1
            and cell not in occupied
        )
        self.assertGreaterEqual(len(adjacent), 2)
        move_registered_actor(fight, seed, adjacent[0])
        other_plant = fight.actors[-8]
        move_registered_actor(fight, other_plant, adjacent[1])

        def prepare(target):
            body = struct.pack(">qqiih", player.id, 5599, *target.position)
            return prepare_server_spell(
                body,
                case.characters[player.id],
                case.monsters,
                fight,
                player.owner_id,
                case.decks[player.id],
                action_id=case.runtime.action_id + 1,
                critical=False,
                line_of_sight=lambda source_cell, target_cell, candidate: authoritative_visible(
                    case.map_id,
                    source_cell,
                    target_cell,
                    candidate,
                    blocking_footprints={
                        actor.id: footprint(actor.position, actor.physical_radius)
                        for actor in candidate.actors.values()
                        if actor.hp > 0
                    },
                ),
                **case.common,
            )

        before = (player.ap, player.mp, player.effect_stats[4], seed.hp)
        tx = prepare(seed)
        self.assertEqual(
            tx.plan["costs"],
            dict(
                ap=0,
                mp=0,
                wp=0,
                conditional_rules=0,
                extra_resource_values={},
                extra_resource_deltas={},
            ),
        )
        self.assertEqual(tx.plan["spell_id"], 5599)
        self.assertEqual(tx.plan["evaluation_level"], 1)
        packets = commit_spell_transaction(
            case.runtime, tx, stats_serializer=case.stats
        )
        self.assertTrue(packets)
        # Delivery preparation leaves the source untouched. The actual native
        # execution result belongs to the prepared transaction candidate.
        killed_seed = tx.fight.actors[seed.id]
        self.assertEqual(killed_seed.hp, 0)
        from wakfu_server.combat_ordinary_death import registered_ordinary_death

        self.assertTrue(registered_ordinary_death(tx.fight, killed_seed))
        self.assertTrue(
            any(
                event.get("kind") == "kill_hp_minimum_update"
                and event.get("generic_effect") == 173894
                and event.get("source_id") == player.id
                and event.get("target_id") == seed.id
                for event in tx.fight.events
            )
        )
        self.assertEqual(seed.hp, before[3])
        self.assertEqual(fight.phase, "active")
        self.assertEqual((player.ap, player.mp, player.effect_stats[4]), before[:3])

        # Same range and owner, wrong native breed fails the original criterion
        # before payment; no synthetic cast result is supplied.
        resources = (player.ap, player.mp, player.effect_stats[4])
        with self.assertRaisesRegex(ValueError, "twV"):
            prepare(other_plant)
        self.assertEqual((player.ap, player.mp, player.effect_stats[4]), resources)


if __name__ == "__main__":
    unittest.main()
