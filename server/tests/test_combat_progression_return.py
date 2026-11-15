"""Progression wire delivery is fenced by the authenticated fight return."""

import struct
import unittest
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_lifecycle import return_to_world
from wakfu_server.combat_progression_delivery import defer


class CombatProgressionReturnTests(unittest.TestCase):
    def test_matching_return_delivers_once_and_duplicate_health_receipt_is_empty(self):
        fight_id, account_id, generation, character_id = 611, 260, 7, 328
        fight = SimpleNamespace(
            id=fight_id,
            phase="finished",
            actors={
                character_id: SimpleNamespace(
                    id=character_id, controlled=True, owner_id=account_id
                )
            },
        )
        deferred = (
            (13832, struct.pack(">qi", character_id, 10611)),
            (13422, struct.pack(">qiq", character_id, 5143, 123)),
            (13832, struct.pack(">qi", character_id, 10616)),
            (13371, struct.pack(">qiB", character_id, 5160, 1)),
        )
        defer(fight, account_id, generation, character_id, deferred)
        runtime = SimpleNamespace(fight=fight)
        store = SimpleNamespace(connection=lambda: nullcontext(object()))
        character = {"id": character_id, "hp": 42, "kamas": 8}
        persisted = {"character": character, "coefficient": 1.0, "applied": True}
        duplicate = {"character": character, "coefficient": 1.0, "applied": False}

        with (
            patch(
                "wakfu_server.combat_health.persist_owned",
                side_effect=[persisted, duplicate],
            ) as persist,
            patch("wakfu_server.combat_results.continuation"),
            patch(
                "wakfu_server.combat_lifecycle.outside_progression",
                return_value=(13052, b"world"),
            ),
            patch(
                "wakfu_server.combat_lifecycle.health.packet",
                return_value=b"health",
            ),
            patch(
                "wakfu_server.combat_lifecycle.wire.account_kamas",
                return_value=b"wallet",
            ),
        ):
            result = return_to_world(
                store,
                account_id,
                generation,
                character,
                runtime,
                struct.pack(">iB", fight_id, 0),
                wp=6,
            )
            repeated = return_to_world(
                store,
                account_id,
                generation,
                character,
                runtime,
                struct.pack(">iB", fight_id, 0),
                wp=6,
            )

        self.assertTrue(result["applied"])
        clear_fight = (13046, struct.pack(">qhBi", character_id, 5, 17, -1))
        self.assertEqual(result["packets"][0], clear_fight)
        self.assertEqual(result["packets"][1:5], list(deferred))
        self.assertFalse(repeated["applied"])
        self.assertEqual(repeated["packets"], [])
        self.assertEqual(persist.call_count, 2)


if __name__ == "__main__":
    unittest.main()
