"""Native first-year reward must unlock the actual common active, not consume paper."""

import struct
import unittest
from random import Random
from unittest.mock import patch


class SchoolSpellRewardTests(unittest.TestCase):
    def test_real_native_master_of_weapons_cast_applies_original_state_and_cost(self):
        from school_spell_domain_fixture import school_spell_domain
        from test_combat_spell_transaction import SpellTransactionTests
        from wakfu_server.spells import encode_deck, owned_spell_records
        from wakfu_server.combat_server_spell import prepare_server_spell

        with school_spell_domain() as source:
            self.assertEqual(source["spell_references"], [5622, 5623])
            character, monster, fight = SpellTransactionTests().native_server_fixture(
                8, 30, native_qi=True, full_health=True
            )
            scroll = dict(
                account_id=character["account_id"], reference=26345, quantity=1
            )
            character["account_quest_items"] = [scroll]
            self.assertIn(
                (character["id"] << 32 | 5622, 5622, 30), owned_spell_records(character)
            )
            ap = fight.actors[7].ap
            result = prepare_server_spell(
                struct.pack(">qqiih", 7, (7 << 32) | 5622, *fight.actors[7].position),
                character,
                {-7: monster},
                fight,
                character["account_id"],
                encode_deck([5622]),
                action_id=1,
                line_of_sight=lambda *args: True,
                critical=False,
                rng=Random(17),
            )
            self.assertEqual(result.fight.actors[7].ap, ap - 2)
            self.assertEqual(
                [
                    (s.reference, s.level)
                    for s in result.fight.actors[7].state_ledger.entries
                    if s.reference == 4092
                ],
                [(4092, 100)],
            )
            self.assertEqual(character["account_quest_items"], [scroll])
            self.assertEqual(fight.actors[7].ap, ap)
            without = dict(character, account_quest_items=[])
            self.assertNotIn(5622, {r[1] for r in owned_spell_records(without)})
            below = dict(character, level=29)
            self.assertNotIn(5622, {r[1] for r in owned_spell_records(below)})

    def test_unpublished_master_domain_and_unknown_spell_reward_remain_unavailable(
        self,
    ):
        from wakfu_server import spells
        from wakfu_server.achievements import rewards

        character = dict(
            id=7,
            account_id=3,
            breed=8,
            level=30,
            account_quest_items=[dict(account_id=3, reference=26345, quantity=1)],
        )
        with patch.object(
            spells, "published_item_spell_references", return_value=frozenset({5623})
        ):
            self.assertNotIn(
                5622, {r[1] for r in spells.owned_spell_records(character)}
            )
        self.assertEqual(
            rewards.validate(dict(d=4382, aeV=16, ckk=False, ckl=[5622])), (16, (5622,))
        )
        self.assertEqual(
            rewards.validate(dict(d=4382, aeV=16, ckk=False, ckl=[5621])),
            (16, (5621,)),
        )
        for reference in (6327, True):
            with self.subTest(reference=reference), self.assertRaises(ValueError):
                rewards.validate(dict(d=4382, aeV=16, ckk=False, ckl=[reference]))

    def test_school_certificate_unlocks_native5621_passive_without_consuming_it(self):
        from protocol_codec import Reader
        from wakfu_server import spells
        from wakfu_server.achievements import rewards
        from wakfu_server.combat_class_initialization import install, plan
        from wakfu_server.spell_audit import catalog, states_catalog

        certificate = dict(account_id=3, reference=26346, quantity=1)
        character = dict(
            id=7,
            account_id=3,
            breed=8,
            level=80,
            x=0,
            y=0,
            z=0,
            account_quest_items=[certificate],
            builds={},
        )

        def known(character):
            return {
                row["id"] for row in spells.item_spells(character, character["level"])
            }

        self.assertIn(5621, spells.published_item_spell_references())
        self.assertNotIn(5621, known(dict(character, account_quest_items=[])))
        self.assertNotIn(
            5621,
            known(
                dict(
                    character,
                    account_quest_items=[
                        dict(account_id=99, reference=26346, quantity=1)
                    ],
                )
            ),
        )
        below = dict(character, level=79)
        self.assertNotIn(5621, known(below))
        with self.assertRaises(ValueError):
            spells.validate_deck(
                spells.encode_deck((), (5621,)), 8, 79, character=below
            )

        deck = spells.encode_deck((), (5621,))
        self.assertEqual(
            spells.validate_deck(deck, 8, 80, character=character)["passive"], [5621]
        )
        for invalid_deck in (
            spells.encode_deck((5621,)),
            spells.encode_deck((), (5621,), 70),
        ):
            with self.subTest(invalid_deck=invalid_deck), self.assertRaises(ValueError):
                spells.validate_deck(invalid_deck, 8, 80, character=character)

        lost_certificate = dict(
            character,
            account_quest_items=[],
            builds={0: {"deck": deck.hex()}},
        )
        reconciled = spells.reconcile_item_spell_decks(lost_certificate)
        self.assertEqual(character["account_quest_items"], [certificate])
        self.assertEqual(lost_certificate["builds"][0]["deck"], deck.hex())
        projected = Reader(bytes.fromhex(reconciled["builds"][0]["deck"]))
        self.assertEqual(projected.number("i"), 0)
        self.assertEqual(projected.number("i"), 1)
        self.assertEqual(projected.number("i"), 0)
        projected.number("i")  # level cap
        projected.finish()
        self.assertEqual(
            spells.validate_deck(deck, 8, 80, character=character)["passive"],
            [5621],
        )

        catalog_data, state_data = catalog(), states_catalog()
        initialization = plan(character, deck, catalog_data, state_data)
        expected_roots = [174742, 174493, 174491, 174744]
        self.assertEqual(
            [entry.reference for entry in initialization.passive_invocations],
            expected_roots,
        )
        self.assertEqual(initialization.passive_sources, (5621,) * 4)
        installed = []
        install(
            initialization,
            install_innate=lambda *_args: None,
            install_passive=lambda source, invocation: installed.append(
                (source, invocation.reference)
            ),
        )
        self.assertEqual(installed, [(5621, root) for root in expected_roots])
        self.assertEqual(character["account_quest_items"], [certificate])

        reward = dict(d=4381, aeV=16, ckk=False, ckl=[5621])
        entitlement = dict(
            achievement_id=2787,
            cycle_key="once",
            reward_key="4381",
            payload=reward,
        )

        class RewardDB:
            def __init__(self, delivered_at=None):
                self.delivered_at = delivered_at

            def execute(self, *_args, **_kwargs):
                return self

            def fetchone(self):
                return dict(payload=reward, delivered_at=self.delivered_at)

        packets = rewards._spell(RewardDB(), character, reward, entitlement)
        self.assertEqual(len(packets), 1)
        self.assertEqual(
            struct.unpack(">qiqh", packets[0][1]),
            (7, 5621, (7 << 32) | 5621, 80),
        )
        self.assertEqual(
            rewards._spell(
                RewardDB(delivered_at="already delivered"),
                character,
                reward,
                entitlement,
            ),
            [],
        )
        with self.assertRaisesRegex(ValueError, "earned outbox entitlement"):
            rewards._spell(RewardDB(), character, reward, None)
