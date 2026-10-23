"""Original player EQUIP predicates use explicit authoritative actor context."""
import ast
import unittest

from wakfu_server.equipment_conditions import catalog, evaluate
from wakfu_server.combat_conditions import _NATIVE_BREED_NAMES
from wakfu_server.combat_local_criteria import parse_local_criterion


class PlayerEquipmentConditionTests(unittest.TestCase):
    def context(self, **changes):
        value = dict(
            actor_kind="player", level=100, real_level=150, breed_id=1, is_admin=False
        )
        value.update(changes)
        return value

    def check(self, text, *, context=None, selected=(), current=(), owned=None):
        return evaluate(
            text,
            item=dict(uid=1, reference=999),
            selected=selected,
            owned={} if owned is None else owned,
            current_equipped=current,
            criterion_context=self.context() if context is None else context,
        )

    def test_all_original_breed_only_templates_use_actual_player_class(self):
        rows = [
            (ref, row["EQUIP"])
            for ref, row in catalog().items()
            if "IsBreed(" in row.get("EQUIP", "")
        ]
        self.assertGreaterEqual(len(rows), 125)
        for ref, criterion in rows:
            calls = [
                node
                for node in ast.walk(parse_local_criterion(criterion))
                if isinstance(node, ast.Call)
            ]
            if any(node.func.id != "IsBreed" for node in calls):
                continue
            for name, breed in _NATIVE_BREED_NAMES.items():
                with self.subTest(ref=ref, breed=name):
                    names = {
                        arg.value.upper()
                        for node in calls
                        for arg in node.args
                        if isinstance(arg, ast.Constant) and type(arg.value) is str
                    }
                    self.assertEqual(
                        self.check(criterion, context=self.context(breed_id=breed)),
                        name in names,
                    )
        self.assertTrue(self.check('IsBreed("feca", "target", "caster")'))
        self.assertFalse(self.check('IsBreed("unknown")'))
        with self.assertRaises(ValueError):
            self.check(
                'IsBreed("FECA")',
                context=dict(actor_kind="native_companion_npc", level=150),
            )

    def test_distinct_real_and_effective_levels_and_actual_admin_authority(self):
        self.assertTrue(self.check("GetRealLevel() == 150 and GetLevel() == 100"))
        self.assertFalse(self.check("GetRealLevel() == GetLevel()"))
        rows = [
            row["EQUIP"]
            for row in catalog().values()
            if row.get("EQUIP", "").strip() == "IsAdmin()"
        ]
        self.assertEqual(len(rows), 57)
        for criterion in rows:
            self.assertFalse(self.check(criterion))
            self.assertTrue(self.check(criterion, context=self.context(is_admin=True)))
        self.assertTrue(
            self.check(
                "GetLevel() == 125", context=dict(actor_kind="player", level=125)
            )
        )
        for predicate in ("IsAdmin()", 'IsBreed("FECA")', "GetRealLevel() == 125"):
            with self.assertRaises(ValueError):
                self.check(predicate, context=dict(actor_kind="player", level=125))
        for changes in (
            dict(is_admin=None),
            dict(breed_id=None),
            dict(real_level=None),
        ):
            with self.assertRaises(ValueError):
                self.check("True", context=self.context(**changes))

    def test_has_equipment_id_uses_equipped_units_and_never_bag_items(self):
        item = dict(uid=2, reference=26575)
        self.assertFalse(self.check("HasEquipmentId(26575)", owned={2: item}))
        self.assertTrue(
            self.check(
                "HasEquipmentId(26575)", owned={2: item}, selected=[dict(uid=2, slot=7)]
            )
        )
        self.assertTrue(
            self.check(
                "HasEquipmentId(26575)", owned={2: item}, current=[dict(uid=2, slot=7)]
            )
        )
        with self.assertRaises(ValueError):
            self.check("HasEquipmentId(26575)", selected=[dict(uid=2, slot=7)])

    def test_two_original_empty_slot_templates_return_reference_or_minus_one(self):
        rows = [
            row["EQUIP"]
            for row in catalog().values()
            if "GetEquipment(" in row.get("EQUIP", "")
        ]
        self.assertEqual(len(rows), 2)
        for criterion in rows:
            self.assertTrue(self.check(criterion))
            self.assertFalse(
                self.check(
                    criterion,
                    selected=[dict(uid=2, slot=0)],
                    owned={2: dict(reference=123)},
                )
            )
        self.assertTrue(
            self.check(
                "GetEquipment(0) == 123",
                selected=[dict(uid=2, slot=0)],
                owned={2: dict(reference=123)},
            )
        )
        self.assertTrue(
            self.check(
                "GetEquipment(0) == 123",
                selected=[dict(uid=2, slot=0)],
                current=[dict(uid=3, slot=0)],
                owned={2: dict(reference=123), 3: dict(reference=456)},
            )
        )
        self.assertTrue(
            self.check(
                "GetEquipment(3) == 456",
                current=[dict(uid=3, slot=3)],
                owned={3: dict(reference=456)},
            )
        )
        with self.assertRaises(ValueError):
            self.check("GetEquipment(0) == -1", selected=[dict(uid=2, slot=0)])
