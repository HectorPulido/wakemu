import unittest
from caster_empty_anchor import prefer_caster_empty_anchors


class CasterEmptyAnchorTests(unittest.TestCase):
    def setUp(self):
        self.effects = {"1": {"native_target_selector": {"class": "fcE", "mask": 2}}}
        self.roots = {
            "1": {
                "native_casting_collision_area": None,
                "native_selector_present": True,
                "native_target_selector": {"class": "fcE", "mask": 2},
            }
        }
        self.calls = []

    def choose(self, **changes):
        args = dict(
            fight=object(),
            source=(0, 0, 0),
            minimum=1,
            maximum=3,
            casting={},
            root_ids=[1],
            effects=self.effects,
            casting_roots=self.roots,
            enumerate_empty=lambda *a, **k: self.calls.append((a, k))
            or [(1, 0, 0), (2, 0, 0), (3, 0, 0)],
        )
        args.update(changes)
        return prefer_caster_empty_anchors(**args)

    def test_exact_caster_root_reuses_two_empty_slots(self):
        self.assertEqual(self.choose(), [(1, 0, 0), (2, 0, 0)])
        self.assertEqual(self.calls[0][1]["limit"], 12)

    def test_ally_only_and_area_selectors_do_not_get_reordered(self):
        for mask in [128, 3, 9]:
            self.effects["1"]["native_target_selector"]["mask"] = mask
            self.roots["1"]["native_target_selector"]["mask"] = mask
            self.assertIsNone(self.choose())
        self.assertFalse(self.calls)

    def test_missing_shape_authority_or_any_spatial_root_fails_closed(self):
        self.roots["1"].pop("native_casting_collision_area")
        self.assertIsNone(self.choose())
        self.roots["1"]["native_casting_collision_area"] = {"area_class": "anE"}
        self.assertIsNone(self.choose())
        self.assertFalse(self.calls)

    def test_zero_minimum_and_mismatched_native_selector_do_not_change_search(self):
        self.assertIsNone(self.choose(minimum=0))
        self.roots["1"]["native_target_selector"] = {"class": "fcE", "mask": 4}
        self.assertIsNone(self.choose())
        self.assertFalse(self.calls)
