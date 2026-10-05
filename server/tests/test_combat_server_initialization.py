import unittest
from unittest.mock import patch
from random import Random
from wakfu_server.combat_server_spell import (
    prepare_server_initialization,
    server_runtime,
)
from wakfu_server.combat_relative_probability import RelativeGroupAuthority
from wakfu_server.fight_checkpoint_store import snapshot
from wakfu_server.spells import encode_deck
import test_combat_spell_transaction as fixture_module


class ServerInitializationTests(unittest.TestCase):
    def setUp(self):
        fixture = fixture_module.SpellTransactionTests()
        self.character, monster, self.fight = fixture.native_server_fixture(16, 60)
        self.monsters = {monster["id"]: monster}
        self.deck = encode_deck((), [6936])

    def test_server_initialization_uses_relative_provider_and_never_double_installs(
        self,
    ):
        before = snapshot(self.fight)
        seen = []
        original = RelativeGroupAuthority.__call__

        def capture(provider, *args):
            seen.append(args[2]["effect_class"])
            return original(provider, *args)

        with patch.object(RelativeGroupAuthority, "__call__", capture):
            preview, packets = prepare_server_initialization(
                self.character,
                self.monsters,
                self.fight,
                3,
                self.deck,
                action_id=1,
                rng=Random(7),
            )
        self.assertIn(999, seen)
        self.assertTrue(preview.native_class_initializations)
        self.assertTrue(packets)
        self.assertEqual(snapshot(self.fight), before)
        stable = snapshot(preview)
        with self.assertRaises(ValueError):
            prepare_server_initialization(
                self.character,
                self.monsters,
                preview,
                3,
                self.deck,
                action_id=2,
                rng=Random(7),
            )
        self.assertEqual(snapshot(preview), stable)

    def test_unsupported_relative_child_rolls_back_earlier_innates(self):
        before = snapshot(self.fight)
        with patch.object(
            RelativeGroupAuthority,
            "__call__",
            side_effect=ValueError("Native population unavailable"),
        ):
            with self.assertRaisesRegex(ValueError, "population unavailable"):
                prepare_server_initialization(
                    self.character,
                    self.monsters,
                    self.fight,
                    3,
                    self.deck,
                    action_id=1,
                    rng=Random(7),
                )
        self.assertEqual(snapshot(self.fight), before)

    def test_real_sacro_start_passive_applies_state_3231_without_forcing_child(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(11, 20)
        deck = encode_deck((), [5051])
        before = snapshot(fight)
        installed, _ = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
        )
        self.assertFalse(installed.native_start_event_delivered)
        self.assertNotIn(
            3231, {s.reference for s in installed.actors[7].state_ledger.entries}
        )
        started, packets = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        self.assertTrue(started.native_start_event_delivered)
        self.assertIn(
            3231, {s.reference for s in started.actors[7].state_ledger.entries}
        )
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)

    def test_real_iop_start_passive_changes_hp_maximum_without_forcing_child(self):
        fixture = fixture_module.SpellTransactionTests()
        character, monster, fight = fixture.native_server_fixture(8, 20)
        deck = encode_deck((), [4795])
        before = snapshot(fight)
        installed, _ = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
        )
        started, packets = prepare_server_initialization(
            character,
            {monster["id"]: monster},
            fight,
            3,
            deck,
            action_id=1,
            rng=Random(7),
            fight_start=True,
        )
        self.assertTrue(started.native_start_event_delivered)
        self.assertGreater(started.actors[7].max_hp, installed.actors[7].max_hp)
        self.assertTrue(packets)
        self.assertEqual(snapshot(fight), before)

    def test_start_failure_discards_initialization_and_uid_changes(self):
        before = snapshot(self.fight)
        with patch(
            "wakfu_server.combat_start_events.deliver_fight_start",
            side_effect=ValueError("Native start child unavailable"),
        ):
            with self.assertRaisesRegex(ValueError, "start child unavailable"):
                prepare_server_initialization(
                    self.character,
                    self.monsters,
                    self.fight,
                    3,
                    self.deck,
                    action_id=1,
                    rng=Random(7),
                    fight_start=True,
                )
        self.assertEqual(snapshot(self.fight), before)

    def test_common_factory_combines_catalog_and_keeps_passive_deck_owned(self):
        factory, adapter = server_runtime(
            self.character,
            self.monsters,
            self.deck,
            action_id=1,
            critical=False,
            rng=Random(7),
        )
        self.assertIsInstance(factory.relative_group_children, RelativeGroupAuthority)
        self.assertIs(factory.relative_group_children.effects, factory.effects)
        self.assertIn(6936, adapter.actor_authority.decks[7])
