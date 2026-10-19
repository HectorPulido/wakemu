"""Voodoll's actual tree action armors only native adjacent friendly recipients."""
import math
import os
import unittest

import test_sadida_grant_pipeline as grants
import test_sadida_super_voodoll_actions_pipeline as actions
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(
    os.environ.get("WAKFU_TEST_GRANTEDCAST") == "1", "native runtime opt-in"
)
class SadidaTreeArmorConsequencesTests(unittest.TestCase):
    def test_actual_tree_armor_matches_owner_max_hp_and_exact_adjacent_recipients(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        from wakfu_server.combat_parameters import _float32

        helper = grants.SadidaGrantPipelineTests()
        data = helper.fixture()
        tx = helper.cast(data, 926, target=data[2].actors[-7].position)
        data = (*data[:2], tx.fight, *data[3:])
        vudul = next(
            a
            for a in data[2].actors.values()
            if getattr(a, "native_summon_source", None)
            and a.hp > 0
            and actor_action_book(a)["profile"] == 3745
        )
        for _ in range(30):
            if data[2].current.id == vudul.id:
                break
            turns.AniripsaGrantSummonPipelineTests().end_current_turn(data[2], data[:5])
        self.assertEqual(data[2].current.id, vudul.id)
        before_position, before_mp = vudul.position, vudul.mp
        data[2].move(vudul.owner_id, vudul.id, [(-7, -8, -1)])
        self.assertEqual(vudul.position, (-7, -8, -1))
        self.assertEqual(vudul.mp, before_mp - 1)
        self.assertNotEqual(vudul.position, before_position)
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2], data[:5])
        seed_cell = (-7, -7, -1)
        self.assertFalse(
            any(a.hp > 0 and a.position == seed_cell for a in data[2].actors.values())
        )
        tx = helper.cast(data, 8137, target=seed_cell)
        data = (*data[:2], tx.fight, *data[3:])
        tx = helper.cast(data, 8137, target=seed_cell, action_id=11)
        data = (*data[:2], tx.fight, *data[3:])
        self.assertGreater(data[2].actors[vudul.id].hp, 0)
        tree = next(
            a
            for a in data[2].actors.values()
            if getattr(a, "native_summon_source", None)
            and a.hp > 0
            and actor_action_book(a)["profile"] == 5577
        )
        for _ in range(30):
            if data[2].current.id == vudul.id:
                break
            turns.AniripsaGrantSummonPipelineTests().end_current_turn(data[2], data[:5])
        self.assertEqual(data[2].current.id, vudul.id)
        fight = data[2]
        vudul = fight.actors[vudul.id]
        owner = fight.actors[7]
        # Native378745: eYs mode1 uses MAX_HP + MAX_VIRTUAL_HP; native
        # float32 coefficient0.05 and nearest rounding, then1013 base0+level.
        expected = math.floor(
            _float32(_float32(0.05) * (owner.max_hp + owner.effect_maxima[92])) + 0.5
        )
        before = {a.id: a.effect_stats[97] for a in fight.actors.values()}
        resources = vudul.ap, vudul.mp, vudul.effect_stats[4]
        expected_ids = {
            a.id
            for a in fight.actors.values()
            if a.hp > 0
            and a.team == vudul.team
            and max(
                abs(a.position[0] - tree.position[0]),
                abs(a.position[1] - tree.position[1]),
            )
            == 1
        }
        self.assertEqual(vudul.effect_stats[120], 0)
        for key in expected_ids:
            self.assertEqual(fight.actors[key].effect_stats[121], 0)
        self.assertIn(7, expected_ids)
        self.assertNotIn(-7, expected_ids)
        tx = actions.SadidaSuperVoodollActionsPipelineTests().summon_cast(
            data, vudul.id, 8140, tree.position
        )
        self.assertEqual(
            tuple(tx.plan["costs"][key] for key in ("ap", "mp", "wp")), (3, 0, 0)
        )
        source = tx.fight.actors[vudul.id]
        self.assertEqual(
            (source.ap, source.mp, source.effect_stats[4]),
            (resources[0] - 3, resources[1], resources[2]),
        )
        deltas = {
            a.id: a.effect_stats[97] - before[a.id] for a in tx.fight.actors.values()
        }
        self.assertEqual(
            {key for key, value in deltas.items() if value > 0}, expected_ids
        )
        for key, delta in deltas.items():
            self.assertEqual(
                delta, expected if key in expected_ids else 0, (key, deltas, expected)
            )
        self.assertEqual(tx.fight.actors[tree.id].position, tree.position)
        self.assertEqual(tx.fight.actors[vudul.id].position, vudul.position)
