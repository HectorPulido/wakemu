"""Actual Voodoll action on an actually acquired native tree."""
import os
import unittest
import test_sadida_grant_pipeline as grants
import test_sadida_super_voodoll_actions_pipeline as actions
import test_aniripsa_grant_summon_pipeline as turns


@unittest.skipUnless(os.environ.get('WAKFU_TEST_GRANTEDCAST') == '1','native runtime opt-in')
class SadidaVoodollTreeActionPipelineTests(unittest.TestCase):
    def test_actual_8140_tree_branch_produces_armor(self):
        from wakfu_server.combat_summon_spellbook import actor_action_book
        helper = grants.SadidaGrantPipelineTests()
        data = helper.fixture()
        tx = helper.cast(data,8137)
        data = (*data[:2],tx.fight,*data[3:])
        cell = next(row['cell'] for row in data[2].native_effect_areas.values()
                    if row['reference']==1835)
        tx = helper.cast(data,8137,target=cell,action_id=11)
        data = (*data[:2],tx.fight,*data[3:])
        tree = next(a for a in data[2].actors.values()
                    if getattr(a,'native_summon_source',None) and a.hp>0
                    and actor_action_book(a)['profile']==5577)
        turns.AniripsaGrantSummonPipelineTests().next_player_turn(data[2],data[:5])
        tx = helper.cast(data,926,action_id=12)
        data = (*data[:2],tx.fight,*data[3:])
        vudul = next(a for a in data[2].actors.values()
                     if getattr(a,'native_summon_source',None) and a.hp>0
                     and actor_action_book(a)['profile']==3745)
        before = {a.id:a.effect_stats.get(97,0) for a in data[2].actors.values()}
        tx = actions.SadidaSuperVoodollActionsPipelineTests().summon_cast(
            data,vudul.id,8140,tree.position)
        self.assertTrue(any(a.effect_stats.get(97,0)>before.get(a.id,0)
                            for a in tx.fight.actors.values()))
        self.assertEqual(tx.fight.actors[-7].effect_stats.get(97,0),before[-7])
