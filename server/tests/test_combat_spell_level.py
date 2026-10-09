import unittest
from wakfu_server.combat_conditions import (
    ConditionContext,
    UnknownCondition,
    evaluate_condition,
)
from wakfu_server.combat_spell_level import NativeSpellBook


class NativeSpellLevelTests(unittest.TestCase):
    def test_lookup_distinguishes_null_missing_and_player_progression(self):
        self.assertEqual(NativeSpellBook(None, True).level(20), 0)
        self.assertEqual(NativeSpellBook({}, True, {}).level(20), 0)
        self.assertEqual(NativeSpellBook({20: 1}, True).level(20), -1)
        self.assertEqual(NativeSpellBook({20: 1}, True, {20: 2}, 1).level(20), 1)
        self.assertEqual(NativeSpellBook({20: 2}, False).level(20), 2)

    def test_predicate_uses_owned_rank_without_deck_inference(self):
        book = NativeSpellBook({6271: 1}, True, {6271: 1})
        context = ConditionContext(
            {}, spell_level_query=lambda reference, selector: book.level(reference)
        )
        self.assertTrue(evaluate_condition('GetSpellLevel(6271,"caster")==1', context))
        self.assertTrue(
            evaluate_condition('GetSpellLevel(999999,"caster")==0', context)
        )
        self.assertTrue(
            evaluate_condition('GetSpellLevel(4294973567,"caster")==1', context)
        )

    def test_missing_authority_remains_unknown(self):
        with self.assertRaisesRegex(UnknownCondition, "spellbook authority"):
            evaluate_condition('GetSpellLevel(6271,"caster")==1', ConditionContext({}))
        with self.assertRaises(UnknownCondition):
            evaluate_condition('GetSpellLevel(1,"unknown",2)==0', ConditionContext({}))

    def test_shared_owned_records_match_wire_without_passive_normalization(self):
        import struct
        from wakfu_server.spells import owned_spell_records, spell_inventory, SPELLS

        character = {"id": 22, "breed": 15, "level": 200}
        records = owned_spell_records(character)
        wire = spell_inventory(character)
        self.assertEqual(struct.unpack_from(">H", wire)[0], len(records))
        decoded = tuple(
            struct.unpack_from(">qih", wire, 2 + index * 14)
            for index in range(len(records))
        )
        self.assertEqual(decoded, records)
        passive = [
            record for record in records if SPELLS[record[1]]["kind"] == "passive"
        ]
        self.assertTrue(passive)
        self.assertTrue(all(record[2] == 200 for record in passive))

    def test_native_decode_clamps_only_to_definition_maximum(self):
        from wakfu_server.combat_spell_level import decoded_spell_levels

        self.assertEqual(
            decoded_spell_levels(
                ((10, 20, 200), (11, 21, 1)),
                {"20": {"maximum_level": 2}, "21": {"maximum_level": 245}},
            ),
            {20: 2, 21: 1},
        )
        with self.assertRaisesRegex(ValueError, "maximum level"):
            decoded_spell_levels(((10, 20, 200),), {})
