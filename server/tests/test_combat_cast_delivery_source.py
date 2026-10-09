"""Shared cast inputs must remain bound to the connected player."""
import unittest

from wakfu_server.combat_cast_delivery_source import connected_cast_source


class ConnectedCastSourceTests(unittest.TestCase):
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
