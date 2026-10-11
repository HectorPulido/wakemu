"""Ordinary NPC ownership is available to the shared nested spell runtime."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.combat_npc_spellbook import ordinary_npc_spellbook
from wakfu_server.combat_spell_level import NativeSpellBook


class OrdinaryNPCSpellbookTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(id=-200, controlled=False, effective_level=239)
        self.fight = SimpleNamespace(actors={-200: self.actor})
        self.source = dict(id=-200, ref=5641)

    def produce(self, rows):
        with patch(
            "wakfu_server.monsters.native_abilities", return_value=rows
        ) as native:
            book = ordinary_npc_spellbook(self.fight, self.actor, self.source)
            native.assert_called_once_with(5641, 239)
            return book

    def test_reuses_exact_native_levels_without_a_player_deck(self):
        book = self.produce(
            [dict(spell_id=8314, spell_level=239), dict(spell_id=8315, spell_level=0)]
        )
        self.assertIsInstance(book, NativeSpellBook)
        self.assertIs(book.player_character, False)
        self.assertEqual(book.level(8314), 239)
        self.assertEqual(book.level(8315), 0)
        self.assertEqual(book.level(9999), 0)
        self.assertIsNone(book.progression_levels)
        self.assertIsNone(book.deck_cap)

    def test_explicit_empty_native_book_does_not_grant_spells(self):
        book = self.produce([])
        self.assertEqual(book.levels, {})
        self.assertEqual(book.level(8314), 0)

    def test_duplicate_or_invalid_native_rows_reject(self):
        for rows in (
            [dict(spell_id=8314, spell_level=1)] * 2,
            [dict(spell_id=True, spell_level=1)],
            [dict(spell_id=8314, spell_level=32768)],
        ):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                self.produce(rows)

    def test_changed_roster_source_or_player_rejects_before_native_lookup(self):
        with patch("wakfu_server.monsters.native_abilities") as native:
            for change in ("roster", "source", "player"):
                with self.subTest(change=change):
                    self.setUp()
                    if change == "roster":
                        self.fight.actors[-200] = SimpleNamespace(id=-200)
                    elif change == "source":
                        self.source["id"] = -201
                    else:
                        self.actor.controlled = True
                    with self.assertRaises(ValueError):
                        ordinary_npc_spellbook(self.fight, self.actor, self.source)
            native.assert_not_called()


class OrdinaryNPCProviderTests(unittest.TestCase):
    def fixture(self):
        from wakfu_server.combat_state import Actor, Fight
        from wakfu_server.combat_ordinary_authority import OrdinaryActorAuthority

        player = Actor(7, 0, (0, 0, 0), 60, 6, 3, 10, 1, 3, True)
        npc = Actor(-200, 1, (1, 0, 0), 20, 6, 3, 5, 239)
        fight = Fight(
            77,
            [player, npc],
            {player.position, npc.position},
            {0: {player.position}, 1: {npc.position}},
        )
        fight.ready(3)
        authority = OrdinaryActorAuthority(
            characters={
                7: dict(
                    id=7,
                    breed=15,
                    level=1,
                    native_spellbook=NativeSpellBook({}, True, {}),
                )
            },
            monsters={-200: dict(id=-200, ref=5641)},
            decks={7: []},
            excluded_decks={7: []},
            catalog=dict(
                player=dict(fight_properties=[]),
                npc={"5641": dict(fight_properties=[])},
            ),
        )
        return fight, authority

    def test_provider_runs_only_for_actual_ordinary_npc(self):
        fight, authority = self.fixture()
        calls = []
        book = NativeSpellBook({8314: 239}, False)
        authority.npc_spellbook = lambda fight, actor, source: (
            calls.append((fight, actor, source)) or book
        )
        actor = fight.actors[-200]
        result = authority(fight, actor)
        self.assertEqual(result.native_spellbook.level(8314), 239)
        self.assertEqual(calls, [(fight, actor, authority.monsters[-200])])
        authority(fight, fight.actors[7])
        self.assertEqual(len(calls), 1)

    def test_provider_cannot_supply_player_book_or_unknown_authority(self):
        fight, authority = self.fixture()
        for book in (NativeSpellBook({8314: 239}, True), {8314: 239}, None):
            with self.subTest(book=book):
                authority.npc_spellbook = lambda *args: book
                with self.assertRaisesRegex(ValueError, "NPC spellbook authority"):
                    authority(fight, fight.actors[-200])
