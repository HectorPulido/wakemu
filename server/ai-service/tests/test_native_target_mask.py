import unittest
from types import SimpleNamespace

from wakfu_ai.native.native_target_mask import derive_native_target_envelope
from wakfu_server.combat_casting_range import resolve_range


def casting_record(*, maximum=10, conditional_maximum=22):
    return {
        "protected": False,
        "maximum_level": 1,
        "line_of_sight": True,
        "linear": False,
        "free_cell": False,
        "levels": [[0, maximum, []]],
        "costs": [[1, 0, 0]],
        "categories": [41],
        "conditional": [
            {
                "linear": False,
                "line_of_sight": True,
                "levels": [[0, 0, 0]],
                "criteria": "HasState(17, 1)",
                "ranges": [[2, conditional_maximum]],
                "free_cell": False,
                "range_modifiable": True,
                "path_option": False,
                "diagonal": False,
                "linear_path": False,
                "allow_self": False,
            }
        ],
        "range_modifiable": True,
        "path_option": False,
        "diagonal": False,
        "linear_path": False,
        "allow_self": False,
        "forbid_QI_P": False,
        "cast_criterion_raw": "",
        "cast_criterion_native_present": False,
    }


class NativeTargetMaskTests(unittest.TestCase):
    def envelope(self, records, owned, overrides=(), fail_spell=None):
        def current(spell, level):
            if spell == fail_spell:
                raise ValueError("unknown active branch")
            return (
                {
                    "minimum": 3,
                    "maximum": 8,
                    "range_modifiable": True,
                    "categories": tuple(records[str(spell)]["categories"]),
                },
                {"spell": spell, "level": level},
            )

        def resolve(spell, level, rule, context):
            self.assertEqual(context["spell"], spell)
            # Mock the complete native range resolver authority: actor RANGE,
            # category range modifiers, carried state and property 2 were read.
            if rule["range_modifiable"]:
                return {**rule, "maximum": rule["maximum"] + 2 + 1}
            return dict(rule)

        return derive_native_target_envelope(
            actor_id=91,
            origin=(-7, 4, -1),
            owned_spells=owned,
            casting_catalog=records,
            override_categories=set(overrides),
            resolve_current=current,
            resolve_range=resolve,
        )

    def test_uses_current_native_selection_and_every_raw_range_branch(self):
        result = self.envelope({"7001": casting_record()}, {7001: 1})
        self.assertTrue(result["complete"])
        # The conditional branch (22 + mocked native range additions) wins.
        self.assertEqual(result["maximum"], 25)
        self.assertEqual(result["spells"][0]["maximum"], 25)
        self.assertEqual(result["origin"], [-7, 4, -1])
        self.assertEqual(result["metric"], "xy-manhattan")

    def test_catalogued_normal_override_fails_open_without_removing_spell(self):
        result = self.envelope({"7001": casting_record()}, {7001: 1}, {41})
        self.assertFalse(result["complete"])
        self.assertIsNone(result["maximum"])
        self.assertEqual(result["unrestrictedSpellIds"], [7001])
        self.assertEqual(result["spells"][0]["spellId"], 7001)

    def test_unknown_spell_branch_disables_union_mask_but_keeps_other_bounds(self):
        records = {
            "7001": casting_record(),
            "7002": casting_record(maximum=5, conditional_maximum=5),
        }
        result = self.envelope(records, {7001: 1, 7002: 1}, fail_spell=7001)
        self.assertFalse(result["complete"])
        self.assertIsNone(result["maximum"])
        self.assertEqual(result["unknownSpellIds"], [7001])
        rows = {row["spellId"]: row for row in result["spells"]}
        self.assertIsNone(rows[7001]["maximum"])
        self.assertEqual(rows[7002]["maximum"], 11)

    def test_unknown_future_catalog_field_fails_open(self):
        record = casting_record()
        record["futureRangeMode"] = "native-new-mode"
        result = self.envelope({"7001": record}, {7001: 1})
        self.assertFalse(result["complete"])
        self.assertIsNone(result["maximum"])
        self.assertEqual(result["unknownSpellIds"], [7001])

    def test_coordinates_outside_signed_int32_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "safe actor coordinates"):
            derive_native_target_envelope(
                actor_id=91,
                origin=(1 << 31, 4, 0),
                owned_spells={},
                casting_catalog={},
                override_categories=set(),
                resolve_current=lambda *_: None,
                resolve_range=lambda *_: None,
            )

    def test_real_native_range_resolver_applies_category_range_carried_and_cap(self):
        actor = SimpleNamespace(spell_range_modifiers={41: 2})
        caster = SimpleNamespace(
            fight_properties=frozenset(),
            characteristics={"RANGE": 3},
            is_carried=True,
        )
        context = SimpleNamespace(actors={"caster": caster})
        rule = dict(
            minimum=2,
            maximum=10,
            range_modifiable=True,
            categories=(41,),
        )
        self.assertEqual(resolve_range(rule, actor, context)["maximum"], 16)
        caster.fight_properties = frozenset({2})
        self.assertEqual(resolve_range(rule, actor, context)["maximum"], 1)


if __name__ == "__main__":
    unittest.main()
