"""Shared cast inputs must remain bound to the connected player."""
import unittest

from wakfu_server.combat_cast_delivery_source import (
    connected_cast_source,
    connected_action_source,
)


class ConnectedCastSourceTests(unittest.TestCase):
    def test_same_account_hero_uses_own_deck_and_summon_uses_hero_context(self):
        from types import SimpleNamespace

        sources = {12: dict(id=12, account_id=8), 14: dict(id=14, account_id=8)}
        actors = {
            identity: SimpleNamespace(controlled=True, owner_id=8)
            for identity in (12, 14, 100)
        }
        fight = SimpleNamespace(
            actors=actors,
            native_summon_registrations={100: dict(actor_id=100, caster_id=14)},
        )
        decks = {12: b"main", 14: b"hero"}
        self.assertEqual(
            connected_action_source(fight, sources, decks, 12, 8, 14),
            (sources[14], b"hero"),
        )
        self.assertEqual(
            connected_action_source(fight, sources, decks, 12, 8, 100),
            (sources[14], b"hero"),
        )
        actors[14].owner_id = 9
        with self.assertRaises(ValueError):
            connected_action_source(fight, sources, decks, 12, 8, 14)
        with self.assertRaises(ValueError):
            connected_action_source(fight, sources, decks, 12, 8, 100)

    def test_connected_owner_selected_even_with_other_player_sources(self):
        owner = {"id": 12, "account_id": 8}
        other = {"id": 13, "account_id": 9}
        source, deck = connected_cast_source(
            {12: owner, 13: other},
            {12: b"owner", 13: b"other"},
            12,
            8,
        )
        self.assertIs(source, owner)
        self.assertEqual(deck, b"owner")

    def test_missing_foreign_or_mismatched_owner_rejected(self):
        for sources, decks in (
            ({}, {12: b"deck"}),
            ({12: {"id": 12, "account_id": 9}}, {12: b"deck"}),
            ({12: {"id": 13, "account_id": 8}}, {12: b"deck"}),
            ({12: {"id": 12, "account_id": 8}}, {}),
        ):
            with self.subTest(sources=sources, decks=decks):
                with self.assertRaises(ValueError):
                    connected_cast_source(sources, decks, 12, 8)
