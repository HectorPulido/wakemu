"""Native ePo/ePi Qs type and ownership counts."""
import unittest
from unittest.mock import patch
from wakfu_server.combat.combat_glyph_count import native_glyph_count
from wakfu_server.combat.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)


class GlyphCountTests(unittest.TestCase):
    def setUp(self):
        # These criteria contain no characteristic names or catalog lookups.
        aliases = patch(
            "wakfu_server.combat.combat_conditions.canonical_aliases", return_value={}
        )
        aliases.start()
        self.addCleanup(aliases.stop)

    def test_type_and_owner_filter_are_independent(self):
        rows = (
            dict(native_type_id=0, owner_id=7),
            dict(native_type_id=0, owner_id=8),
            dict(native_type_id=19, owner_id=7),
            dict(native_type_id=0, owner_id=None),
        )
        self.assertEqual(native_glyph_count(rows), 3)
        self.assertEqual(native_glyph_count(rows, actor_id=7, filter_owner=True), 1)
        self.assertEqual(native_glyph_count(rows, filter_owner=True), 0)

    def test_unknown_owner_or_type_fail_closed(self):
        with self.assertRaises(ValueError):
            native_glyph_count((dict(owner_id=7),))
        with self.assertRaises(ValueError):
            native_glyph_count((dict(native_type_id=0),), actor_id=7, filter_owner=True)
        self.assertEqual(native_glyph_count((dict(native_type_id=0),)), 1)

    def test_numeric_condition_uses_general_callback(self):
        calls = []

        def count(selector):
            calls.append(selector)
            return 2

        context = ConditionContext({}, glyph_count_query=count)
        for text in (
            "NbGlyphs() == 2",
            'NbGlyphs("caster") < 3',
            'NbGlyphs("triggeringTarget") >= 1',
        ):
            self.assertTrue(evaluate_condition(text, context))
        self.assertEqual(calls, [None, "caster", "triggeringTarget"])

    def test_missing_authority_invalid_arguments_and_boolean_result_reject(self):
        for text in (
            "NbGlyphs() == 0",
            "NbGlyphs(7) == 0",
            'NbGlyphs("caster", 1) == 0',
        ):
            with self.subTest(text=text), self.assertRaises(UnknownCondition):
                evaluate_condition(text, ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition(
                "NbGlyphs() == 1",
                ConditionContext({}, glyph_count_query=lambda _: True),
            )
