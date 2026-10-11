import unittest
from types import SimpleNamespace
from wakfu_server.combat_hud_resource import sync_actor_hud_resource, sync_hud_resources


class HudResourceTests(unittest.TestCase):
    def actor(self, breed=8, levels=(35,)):
        return SimpleNamespace(
            id=1,
            native_hud_breed=breed,
            effect_stats={67: 0, 4: 3, 111: 9},
            state_ledger=SimpleNamespace(
                entries=tuple(SimpleNamespace(reference=3442, level=n) for n in levels)
            ),
        )

    def test_update_remove_and_native_order_are_one_resource(self):
        actor = self.actor(levels=(35, 90))
        self.assertEqual(sync_actor_hud_resource(actor), (1, 67, 0, 35))
        actor.state_ledger.entries = (SimpleNamespace(reference=3442, level=100),)
        self.assertEqual(sync_actor_hud_resource(actor), (1, 67, 35, 100))
        actor.state_ledger.entries = ()
        self.assertEqual(sync_actor_hud_resource(actor), (1, 67, 100, 0))
        self.assertEqual((actor.effect_stats[4], actor.effect_stats[111]), (3, 9))

    def test_unknown_breed_and_metadata_preserve_existing_mechanics(self):
        actor = self.actor(breed=18)
        actor.effect_stats[67] = 18
        self.assertIsNone(sync_actor_hud_resource(actor))
        del actor.native_hud_breed
        self.assertIsNone(sync_actor_hud_resource(actor))
        self.assertEqual(actor.effect_stats[67], 18)

    def test_furor_uses_9312_not_hp_percent_helper_9313(self):
        actor = self.actor(breed=11)
        actor.effect_stats[50] = 0
        actor.state_ledger.entries = (SimpleNamespace(reference=9313, level=100),)
        self.assertIsNone(sync_actor_hud_resource(actor))
        actor.state_ledger.entries += (SimpleNamespace(reference=9312, level=20),)
        self.assertEqual(sync_actor_hud_resource(actor), (1, 50, 0, 20))
        self.assertEqual(actor.effect_stats[67], 0)

    def test_preview_only_and_missing_characteristic_rejects(self):
        from copy import deepcopy

        original = SimpleNamespace(actors={1: self.actor()})
        preview = deepcopy(original)
        self.assertEqual(sync_hud_resources(preview), ((1, 67, 0, 35),))
        self.assertEqual(original.actors[1].effect_stats[67], 0)
        del preview.actors[1].effect_stats[67]
        with self.assertRaises(ValueError):
            sync_hud_resources(preview)


class NativeHudThresholdTests(unittest.TestCase):
    def test_native_concentration_threshold_projects_final_level(self):
        from random import Random
        from copy import deepcopy
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.combat_server_spell import (
            prepare_server_initialization,
            prepare_server_spell,
            server_runtime,
        )
        from wakfu_server.combat_effect_dispatch import EffectInvocation
        from wakfu_server.combat_native_timing_context import NativeEffectTimingProvider
        from wakfu_server.combat_state_managers import state_manager
        from wakfu_server.spells import encode_deck
        from wakfu_server.fight_checkpoint_store import snapshot

        character, monster, fight = SpellTransactionTests().native_server_fixture(
            8,
            21,
            native_qi=True,
            target_ref=4085,
            target_level=23,
        )
        self.assertEqual((fight.actors[-7].effective_level, monster["ref"]), (23, 4085))
        deck = encode_deck([4779])
        ready, _ = prepare_server_initialization(
            character,
            {-7: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        import struct

        # Spend PW through a legal ordinary cast; do not lower the snapshot by hand.
        pos = ready.actors[7].position
        spent = prepare_server_spell(
            struct.pack(">qqiih", 7, (7 << 32) | 4779, *pos),
            character,
            {-7: monster},
            ready,
            3,
            deck,
            action_id=2,
            critical=False,
            line_of_sight=lambda *args: True,
            rng=Random(7),
        ).fight
        self.assertLess(
            spent.actors[7].effect_stats[4], ready.actors[7].effect_stats[4]
        )
        ready = spent
        before = snapshot(ready)
        preview = deepcopy(ready)
        factory, _ = server_runtime(
            character, {-7: monster}, deck, action_id=2, critical=False, rng=Random(7)
        )
        dispatcher, packets = factory(
            preview, {"native_retained_container": {"present": False}}
        )
        invocation = EffectInvocation(2226, 100, 7, 7, preview.actors[7].position)
        context = NativeEffectTimingProvider(
            factory.state_catalog
        ).direct_state_reference(preview, invocation, 3442, 100, critical=False)
        wp = preview.actors[7].effect_stats[4]
        concentration = preview.actors[7].effect_stats[67]
        with preview.effect_resolution():
            dispatcher.native_retention.open_state(invocation)
            try:
                dispatcher.native_state_handler.apply_reference(
                    None,
                    invocation,
                    3442,
                    100,
                    carrier_context=context,
                    protected=False,
                )
            finally:
                dispatcher.native_retention.close_state(invocation)
        levels = [
            e.level
            for e in preview.actors[7].state_ledger.entries
            if e.reference == 3442
        ]
        self.assertEqual(preview.actors[7].effect_stats[67], levels[0] if levels else 0)
        self.assertEqual(preview.actors[7].effect_stats[67], concentration)
        self.assertEqual(preview.actors[7].effect_stats[4], wp + 1)
        self.assertFalse(
            any(
                row["effect_class"] == 193
                for row in preview.owned_stat_effects.values()
            )
        )
        self.assertTrue(packets)
        self.assertEqual(snapshot(ready), before)
