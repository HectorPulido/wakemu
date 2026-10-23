"""Native EQUIP predicates consume an explicit effective-current snapshot."""
import unittest

from wakfu_server.equipment_conditions import catalog, evaluate


class EquipmentGetCharacTests(unittest.TestCase):
    def evaluate(
        self, expression, values, *, reference=4224, duplicate=False, context=None
    ):
        item = dict(uid=101, reference=reference)
        owned = {101: item, 102: dict(uid=102, reference=reference)}
        selected = [dict(uid=101)] + ([dict(uid=102)] if duplicate else [])
        return evaluate(
            expression,
            item=item,
            selected=selected,
            owned=owned,
            criterion_context=context,
            current_characteristics=values,
        )

    def test_complete_133_reference_inventory_preserves_admin_and_duplicate_guards(
        self,
    ):
        rows = [
            (int(ref), actions["EQUIP"])
            for ref, actions in catalog().items()
            if "GetCharac(" in actions.get("EQUIP", "")
        ]
        self.assertEqual(len(rows), 133)
        pure, duplicate, admin = 0, 0, 0
        for reference, expression in rows:
            with self.subTest(reference=reference, expression=expression):
                values = {9: 0, 7: 550, 11: 2, 87: 15, 104: 450, 8: 550, 86: 10}
                if 'GetCharac("TACKLE") >= 400' in expression:
                    values[7] = 450
                if 'GetCharac("FEROCITY") >= 40' in expression:
                    values[9] = 45
                if 'GetCharac("BLOCK") >= 40' in expression:
                    values[87] = 45
                if "IsAdmin(" in expression:
                    admin += 1
                    self.assertEqual(reference, 19525)
                    with self.assertRaises(ValueError):
                        self.evaluate(expression, values, reference=reference)
                    continue
                self.assertIs(
                    self.evaluate(expression, values, reference=reference), True
                )
                if "HasAnotherSameEquipment(" in expression:
                    duplicate += 1
                    self.assertIs(
                        self.evaluate(
                            expression, values, reference=reference, duplicate=True
                        ),
                        False,
                    )
                else:
                    pure += 1
        self.assertEqual((pure, duplicate, admin), (117, 15, 1))

    def test_native_effective_current_boundaries_and_equip_actor_selectors(self):
        expression = 'GetCharac("FEROCITY") > -10'
        # Matches real eQe/eJy +ffh/fff oracle. The last supplied0 is the
        # original effective clamp of rawcurrent-11 with a native lower bound0.
        for current, expected in ((-11, False), (-10, False), (-9, True), (0, True)):
            with self.subTest(current=current):
                self.assertIs(self.evaluate(expression, {9: current}), expected)
        for selector in ("caster", "target", "CASTER", "TaRgEt"):
            with self.subTest(selector=selector):
                self.assertIs(
                    self.evaluate(
                        f'GetCharac("FEROCITY", "{selector}") > -10', {9: -9}
                    ),
                    True,
                )
        self.assertIs(self.evaluate('GetCharac("FEROCITY") >= -9', {9: -9}), True)
        self.assertIs(self.evaluate('GetCharac("FEROCITY") <= -10', {9: -9}), False)

    def test_original_aliases_share_the_exact_native_pc_value(self):
        for alias in ("AP", "ap", "pa", "PA"):
            self.assertIs(self.evaluate(f'GetCharac("{alias}") == 6', {2: 6}), True)
        for alias in ("control", "mechanics", "leadership", "contrôle", "CONTRÔLE"):
            self.assertIs(self.evaluate(f'GetCharac("{alias}") == 3', {12: 3}), True)
        with self.assertRaises(ValueError):
            self.evaluate('GetCharac("NOT_A_NATIVE_PC") == 0', {12: 0})

    def test_missing_unknown_or_malformed_context_never_becomes_zero(self):
        for values in (
            None,
            {},
            {True: 0},
            {9: True},
            {9999: 0},
            {9: 2**31},
            {9: -(2**31) - 1},
            {"9": 0},
        ):
            with self.subTest(values=values), self.assertRaises(ValueError):
                self.evaluate('GetCharac("FEROCITY") > -10', values)
        for expression in (
            'True or GetCharac("FEROCITY") > -10',
            'True or GetCharac("NOT_A_NATIVE_PC") == 0',
            'GetCharac("HP", 1) > 0',
            'GetCharac("HP", "triggeringCaster") > 0',
            'GetCharac("HP", "caster", "target") > 0',
            'GetCharac("__unknown_native_stat__") > 0',
            'GetCharac(name="HP") > 0',
            "True or IsAdmin()",
        ):
            with self.subTest(expression=expression), self.assertRaises(ValueError):
                self.evaluate(expression, {1: 100})

    def test_npc_context_remains_independent_and_explicit(self):
        context = dict(actor_kind="native_companion_npc", level=55)
        self.assertIs(
            self.evaluate(
                'GetRealLevel() >= 50 and GetCharac("FEROCITY") > -10',
                {9: -9},
                context=context,
            ),
            True,
        )
        with self.assertRaises(ValueError):
            self.evaluate("GetRealLevel() > 0", {9: -9})
        with self.assertRaises(ValueError):
            self.evaluate(
                'GetCharac("FEROCITY") > -10',
                {9: -9},
                context=dict(actor_kind="human", level=55),
            )


if __name__ == "__main__":
    unittest.main()
