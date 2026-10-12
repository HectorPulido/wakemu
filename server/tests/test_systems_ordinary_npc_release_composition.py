"""Published NPC ownership must survive actual production runtime composition."""
import unittest
from unittest.mock import patch

import test_combat_npc_attack as attack_fixtures
from wakfu_server.combat_npc_attack import npc_runtime_catalog, npc_spell_catalog
from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook
from wakfu_server.combat_server_spell import server_runtime
from wakfu_server.monsters import native_abilities
from wakfu_server.spells import default_deck


class OrdinaryNPCReleaseCompositionTests(unittest.TestCase):
    def setUp(self):
        self.fixture = attack_fixtures.NativeNpcAttackTests()
        self.fixture.setUp()
        self.assertIn(
            "5525", npc_spell_catalog()["activation_policy"]["enabled_monsters"]
        )

    def test_published_npc_caster_and_player_target_share_native_owned_book(self):
        f = self.fixture
        factory, adapter = server_runtime(
            f.character,
            {f.npc.id: f.monster},
            default_deck(f.character),
            action_id=1,
            critical=False,
            compiled=npc_runtime_catalog(),
        )
        self.assertIsNotNone(factory)
        # Obtain metadata through the actual wrapper installed by server_runtime.
        # The same NPC is a caster in AI and a target in ordinary player casts.
        metadata = adapter.actor_authority(f.fight, f.npc)
        expected = {
            row["spell_id"]: row["spell_level"]
            for row in native_abilities(f.monster["ref"], f.npc.effective_level)
        }
        self.assertFalse(metadata.is_player)
        self.assertIs(metadata.native_spellbook.player_character, False)
        self.assertEqual(metadata.native_spellbook.levels, expected)
        self.assertEqual(metadata.native_spellbook.level(7962), 1)
        self.assertIsNone(metadata.native_spellbook.deck_cap)
        player = adapter.actor_authority(f.fight, f.pc)
        self.assertTrue(player.is_player)
        self.assertIs(player.native_spellbook.player_character, True)
        self.assertEqual(
            adapter.actor_authority(f.fight, f.npc).native_spellbook.levels,
            expected,
        )

    def test_published_attack_invokes_actual_provider_and_preserves_native_damage(self):
        f = self.fixture
        with patch(
            "wakfu_server.combat_npc_spellbook.ordinary_npc_spellbook",
            wraps=ordinary_npc_spellbook,
        ) as provider:
            result = f.run_attack()
        self.assertGreater(provider.call_count, 0)
        for call in provider.call_args_list:
            fight, actor, source = call.args
            self.assertIs(fight.actors[actor.id], actor)
            self.assertFalse(actor.controlled)
            self.assertEqual((source["ref"], source["id"]), (5525, f.npc.id))
        self.assertEqual((f.pc.hp, f.npc.ap), (55, 3))
        self.assertEqual(result["damage"], 5)
        self.assertTrue(result["packets"])
