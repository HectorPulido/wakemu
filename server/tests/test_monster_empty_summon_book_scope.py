"""Empty native dependency books require sealed csd proof and exact parent levels."""
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from monster_summon_book_source import empty_book_source, qualified_empty_book
from prepare_monster_spell_activation import attach_summon_dependencies


class EmptySummonBookScopeTests(unittest.TestCase):
    def receipt(self):
        return empty_book_source(
            3800, dict(ref=3800, native_abilities=[], raw_native=dict(d=3800, csd=[]))
        )

    def test_source_qualified_empty_book_only_adds_parent_dependency_scope(self):
        npc = dict(activation_policy=dict(enabled_monsters={"3924": {}}))
        source = dict(
            level_domain_exact=True,
            descriptor_levels=[38],
            spell_ids=[],
            native_empty_book_source=self.receipt(),
        )
        closure = dict(spell_summon_profiles={"4807": {"3800": source}})
        attach_summon_dependencies(
            npc, [dict(ref=3924, spell_ids=[4807])], closure, 100
        )
        enabled = npc["activation_policy"]["enabled_monsters"]
        self.assertEqual(set(enabled), {"3924"})
        scope = enabled["3924"]["registered_summon_profiles"]["3800"]
        self.assertEqual(scope["spell_ids"], [])
        self.assertEqual(scope["descriptor_levels"], [38])
        self.assertEqual(scope["native_empty_book_source"], self.receipt())

    def test_unknown_empty_wrong_source_and_wrong_book_types_stay_rejected(self):
        for book, receipt in [
            ([], None),
            ([], dict(self.receipt(), profile_reference=5543)),
            ([], dict(self.receipt(), raw_csd=None)),
            (None, None),
            ({}, None),
            ([1, 1], None),
            ([True], None),
        ]:
            npc = dict(activation_policy=dict(enabled_monsters={"3924": {}}))
            source = dict(
                level_domain_exact=True,
                descriptor_levels=[38],
                spell_ids=book,
                native_empty_book_source=receipt,
            )
            with self.assertRaisesRegex(ValueError, "book scope"):
                attach_summon_dependencies(
                    npc,
                    [dict(ref=3924, spell_ids=[4807])],
                    dict(spell_summon_profiles={"4807": {"3800": source}}),
                    100,
                )
            self.assertEqual(npc["activation_policy"]["enabled_monsters"]["3924"], {})

    def test_empty_book_does_not_override_unknown_descriptor_domain(self):
        npc = dict(activation_policy=dict(enabled_monsters={"3924": {}}))
        source = dict(
            level_domain_exact=False,
            descriptor_levels=[38],
            spell_ids=[],
            native_empty_book_source=self.receipt(),
        )
        attach_summon_dependencies(
            npc,
            [dict(ref=3924, spell_ids=[4807])],
            dict(spell_summon_profiles={"4807": {"3800": source}}),
            100,
        )
        self.assertEqual(npc["activation_policy"]["enabled_monsters"]["3924"], {})

    def test_missing_or_inconsistent_raw_native_empty_source_is_unknown(self):
        for profile in [
            dict(ref=3800, native_abilities=[]),
            dict(ref=3800, native_abilities=[], raw_native=dict(d=3800)),
            dict(ref=3800, native_abilities=[], raw_native=dict(d=5543, csd=[])),
            dict(ref=3800, native_abilities=None, raw_native=dict(d=3800, csd=[])),
        ]:
            with self.assertRaises(ValueError):
                empty_book_source(3800, profile)
        self.assertTrue(qualified_empty_book(3800, self.receipt()))
