"""Direct health sequence inference preserves source LIFO execution order."""
from types import SimpleNamespace
import unittest

from wakfu_server.wakia_bridge.wakfu_ai.bridge.jondo_snapshot import direct_health_order


def row(reference, kind):
    return {
        "nativeReference": reference,
        "kind": kind,
        "target": "enemy",
        "conditional": False,
        "probability": 100,
        "nativeBase": {"version": 1},
    }


def compiled(
    *,
    children=(),
    mask_override=None,
    variant=0,
    delay=0,
    duration=0,
    omit_masks=False,
    omit_children=False,
    omit_criteria=False
):
    def effect(effect_children):
        row = {
            "children": list(effect_children),
            "criteria": "",
            "variant": variant,
            "native_execution_mode": 2,
            "native_definition_class": "eVy",
            "target_masks": [[], [], [], [], [], [], []],
            "native_timing_definition": {
                "ryE": duration,
                "ryF": 0,
                "ryH": delay,
                "ryI": 0,
            },
        }
        if mask_override is not None:
            row["target_masks"] = mask_override
        if omit_masks:
            row.pop("target_masks")
        if omit_children:
            row.pop("children")
        if omit_criteria:
            row.pop("criteria")
        return row

    return SimpleNamespace(
        effects={
            "1": effect(children),
            "2": effect(()),
        }
    )


class DirectHealthOrderTests(unittest.TestCase):
    def test_lifo_damage_then_heal_is_reordered_to_root_execution_order(self):
        rows = [row(2, "heal"), row(1, "damage")]

        ordered, certified = direct_health_order(compiled(), [1, 2], rows, [], 1)

        self.assertTrue(certified)
        self.assertEqual([item["kind"] for item in ordered], ["damage", "heal"])

    def test_lifo_heal_then_damage_is_reordered_to_root_execution_order(self):
        rows = [row(2, "damage"), row(1, "heal")]

        ordered, certified = direct_health_order(compiled(), [1, 2], rows, [], 1)

        self.assertTrue(certified)
        self.assertEqual([item["kind"] for item in ordered], ["heal", "damage"])

    def test_duplicate_roots_are_not_certified(self):
        rows = [row(1, "damage"), row(1, "heal")]

        result, certified = direct_health_order(compiled(), [1, 1], rows, [], 1)

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_roots_with_children_are_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(children=(3,)), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_missing_children_field_is_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(omit_children=True), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_missing_criteria_field_is_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(omit_criteria=True), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_unknown_projection_is_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(), [1, 2], rows, ["unknown row"], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_spell_6399_unknown_family_preserves_all_projected_rows_and_order(self):
        roots = [254473, 255653, 254476]
        # Catalogue projection: the first two roots each target ally, enemy,
        # and self. The final family (447) has no projected rows.
        rows = [
            dict(row(255653, "heal"), target="ally"),
            dict(row(255653, "heal"), target="enemy"),
            dict(row(255653, "heal"), target="self"),
            dict(row(254473, "damage"), target="ally"),
            dict(row(254473, "damage"), target="enemy"),
            dict(row(254473, "damage"), target="self"),
        ]
        original_order = [
            (item["nativeReference"], item["kind"], item["target"]) for item in rows
        ]
        compiled_spell = SimpleNamespace(
            effects={
                str(reference): {
                    "children": [],
                    "criteria": "",
                    "variant": 0,
                    "native_execution_mode": 2,
                    "native_definition_class": "eVy",
                    "target_masks": [[], [], [], [], [], [], []],
                    "native_timing_definition": {
                        "ryE": 0,
                        "ryF": 0,
                        "ryH": 0,
                        "ryI": 0,
                    },
                }
                for reference in roots
            }
        )

        result, certified = direct_health_order(
            compiled_spell, roots, rows, ["unsupported_semantic_family:447"], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)
        self.assertEqual(
            [
                (item["nativeReference"], item["kind"], item["target"])
                for item in result
            ],
            original_order,
        )

    def test_missing_rows_are_not_certified(self):
        rows = [row(1, "damage")]

        result, certified = direct_health_order(compiled(), [1, 2], rows, [], 1)

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_subscribed_target_mask_is_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]
        masks = [[], [], [], [], [], [], [42]]

        result, certified = direct_health_order(
            compiled(mask_override=masks), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_missing_target_masks_are_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(omit_masks=True), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_none_mask_is_known_empty_and_is_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]
        masks = [None, None, None, None, None, None, None]

        ordered, certified = direct_health_order(
            compiled(mask_override=masks), [1, 2], rows, [], 1
        )

        self.assertTrue(certified)
        self.assertEqual([item["kind"] for item in ordered], ["damage", "heal"])

    def test_delayed_effects_are_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(compiled(delay=1), [1, 2], rows, [], 1)

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_retained_effects_are_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(duration=2), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)

    def test_nonzero_variant_is_not_certified(self):
        rows = [row(2, "heal"), row(1, "damage")]

        result, certified = direct_health_order(
            compiled(variant=1), [1, 2], rows, [], 1
        )

        self.assertFalse(certified)
        self.assertIs(result, rows)


if __name__ == "__main__":
    unittest.main()
