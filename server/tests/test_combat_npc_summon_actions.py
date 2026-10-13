"""Monster summon routing never invents encounter descriptors or player authority."""
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch
from wakfu_server.combat_npc_summon_actions import (
    monster_creator_context,
    registered_npc_summon_book,
)


class NativeNpcSummonActionTests(unittest.TestCase):
    def fixture(self, *, player=False):
        parent = NS(id=-200, controlled=player)
        child = NS(
            id=3,
            controlled=False,
            native_summon_source={
                "caster_id": -200,
                "native_relation_source": "big.new_bje.fdt_initial_registration",
            },
        )
        fight = NS(actors={-200: parent, 3: child})
        monsters = {-200: {"id": -200, "ref": 87, "map_id": 1134}}
        return fight, child, monsters

    def test_map_authority_comes_from_real_creator_without_child_descriptor(self):
        fight, child, monsters = self.fixture()
        self.assertEqual(
            monster_creator_context(fight, child, monsters),
            {"creator_id": -200, "map_id": 1134},
        )
        self.assertNotIn(child.id, monsters)

    def test_class_created_actor_retains_class_routing(self):
        fight, child, monsters = self.fixture(player=True)
        self.assertIsNone(monster_creator_context(fight, child, monsters))

    def test_missing_actual_creator_is_rejected(self):
        fight, child, monsters = self.fixture()
        del fight.actors[-200]
        with self.assertRaises(ValueError):
            monster_creator_context(fight, child, monsters)

    def test_cyclic_creator_chain_is_rejected(self):
        fight, child, monsters = self.fixture()
        child.native_summon_source["caster_id"] = child.id
        with self.assertRaises(ValueError):
            monster_creator_context(fight, child, monsters)

    def test_changed_encounter_identity_is_rejected(self):
        fight, child, monsters = self.fixture()
        monsters[-200]["id"] = 99
        with self.assertRaises(ValueError):
            monster_creator_context(fight, child, monsters)

    def test_current_native_control_is_required_before_book_authorization(self):
        fight, child, monsters = self.fixture()
        with patch(
            "wakfu_server.combat_effective_control.effective_server_controlled",
            return_value=False,
        ):
            with self.assertRaisesRegex(ValueError, "not currently server controlled"):
                registered_npc_summon_book(fight, child, monsters)
