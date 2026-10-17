"""Genuine native5347 ownership cannot finance any action with its own book.

This is an isolated negative resource-boundary contract, not encounter approval.
The normal native fixture constructs the actor with unchanged native resources.
The shared validator must reject before target selection or effect execution.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))


FIXTURES = Path(__file__).resolve().parent / "fixtures"


class NativeUnpayableOwnedBookTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from validate_monster_spell_activation import fixture

        cls.witness = json.loads(
            (FIXTURES / "combat_operation_native_resources_5347.json").read_text()
        )
        cls.fight, cls.character, cls.monsters, cls.deck = fixture(
            5347, 1, (-9, -7, -1)
        )

    def test_native_constructor_and_complete_owned_book_have_no_wp_producer(self):
        from wakfu_server.combat_npc_spell import owned_spells
        from wakfu_server.combat_npc_attack import npc_spell_catalog
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.monster_minigame_policy import (
            NO_RESOURCE_PRODUCER_BLOCKED_REFERENCES,
            NO_RESOURCE_PRODUCER_REASON,
        )

        captured_path = FIXTURES / "owned-captured-5347-native.json"
        expected_hash = self.witness["source_sha256"][
            "server/tests/fixtures/owned-captured-5347-native.json"
        ]
        self.assertEqual(
            hashlib.sha256(captured_path.read_bytes()).hexdigest(), expected_hash
        )
        captured = json.loads(captured_path.read_text())
        profile = captured["native_profile_export"]["profiles"]["5347"]
        actor_profile = captured["actor_catalog"]["npc_profiles"]["5347"]
        self.assertEqual(profile["initial_state_triples"], [])
        self.assertEqual(actor_profile["at_base_level"]["4"]["current"], 0)
        self.assertEqual(
            self.witness["monster"]["statistics"]["WP"], {"base": 0, "per_level": 0.0}
        )
        self.assertEqual(self.monsters[-200]["wp"], 0)
        self.assertEqual(self.fight.current.id, -200)
        self.assertEqual(self.fight.current.effect_stats[4], 0)
        book = owned_spells(self.fight, self.monsters, character=self.character)
        self.assertEqual(book, {7356: 1, 7357: 1, 7358: 1})
        self.assertEqual({r["reference"] for r in profile["abilities"]}, set(book))
        live_effects = npc_spell_catalog()["effects"]
        reached = set()
        for spell, level in book.items():
            record, index = native_casting_table(spell, level)
            expected = self.witness["spells"][str(spell)]
            self.assertEqual(record["conditional"], [])
            self.assertEqual(record["costs"][index], expected["costs"])
            self.assertEqual(expected["costs"], [0, 0, 1])
            self.assertEqual(record["levels"][index][2], expected["roots"])
            pending = list(expected["roots"])
            while pending:
                reference = pending.pop()
                if reference in reached:
                    continue
                reached.add(reference)
                effect = self.witness["effects"][str(reference)]
                self.assertEqual(
                    {key: live_effects[str(reference)][key] for key in effect}, effect
                )
                self.assertLessEqual(effect["minimum_level"], level)
                self.assertGreaterEqual(effect["maximum_level"], level)
                # These exact leaves are earth/air damage and push/teleport.
                # No state, summon, callback or resource-producing branch exists
                # in this actor's complete owned book at the selected level.
                self.assertIn(effect["effect_class"], (3, 5, 300, 302))
                self.assertEqual(effect["children"], [])
                pending.extend(effect["children"])
        self.assertEqual(reached, {int(k) for k in self.witness["effects"]})
        self.assertEqual(len(reached), 7)
        self.assertIn(5347, NO_RESOURCE_PRODUCER_BLOCKED_REFERENCES)
        self.assertEqual(
            NO_RESOURCE_PRODUCER_REASON,
            "unpayable_native_book_without_resource_producer",
        )

    def test_actual_shared_cost_guard_rejects_all_owned_actions_atomically(self):
        from wakfu_server.combat_cast import _validate_target
        from wakfu_server.combat_geometry_snapshot import source_snapshot
        from wakfu_server.combat_native_spell_casting import native_casting_table
        from wakfu_server.combat_npc_spell import owned_spells

        fight = self.fight
        actor = fight.current
        book = owned_spells(fight, self.monsters, character=self.character)
        before = deepcopy(source_snapshot(fight))
        descriptors_before = deepcopy(self.monsters)
        self.assertEqual(actor.effect_stats[4], 0)
        self.assertEqual((actor.ap, actor.mp), (0, 0))
        for spell, level in book.items():
            with self.subTest(spell=spell, level=level):
                record, index = native_casting_table(spell, level)
                self.assertEqual(record["conditional"], [])
                costs = dict(zip(("ap", "mp", "wp"), record["costs"][index]))
                costs_before = deepcopy(costs)
                roots = tuple(record["levels"][index][2])
                with self.assertRaisesRegex(
                    ValueError, "Insufficient authoritative spell resources"
                ) as rejected:
                    _validate_target(
                        {
                            "actor_id": actor.id,
                            "spell_uid": spell,
                            "target": (-9, -7, -1),
                        },
                        actor,
                        fight,
                        actor.effect_stats[4],
                        costs,
                        {"costs": costs, "roots": roots},
                        roots,
                        level,
                        None,
                        spell,
                        None,
                    )
                error = rejected.exception
                self.assertEqual(error.cast_validation_code, "insufficient_resources")
                self.assertEqual(
                    error.native_resource_diagnostic,
                    {
                        "available": {"ap": 0, "mp": 0, "wp": 0},
                        "required": {"ap": 0, "mp": 0, "wp": 1},
                        "deficits": {"wp": 1},
                    },
                )
                self.assertEqual(costs, costs_before)
                self.assertEqual(source_snapshot(fight), before)
                self.assertEqual(self.monsters, descriptors_before)
                self.assertEqual(actor.effect_stats[4], 0)


if __name__ == "__main__":
    unittest.main()
