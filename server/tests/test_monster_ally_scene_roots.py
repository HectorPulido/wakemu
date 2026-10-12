import unittest
from ally_scene_roots import native_ally_scene_roots


class NativeAllySceneRootsTests(unittest.TestCase):
    def fixture(self):
        return {
            "8368": {
                "maximum_level": 245,
                "levels": [[0, 0, [392568]] for _ in range(245)],
            }
        }, {"392568": {"effect_class": 349}}

    def test_actual_245_casting_domain_independent_of_200_effect_samples(self):
        casting, effects = self.fixture()
        self.assertEqual(
            native_ally_scene_roots(8368, 245, casting, effects), [effects["392568"]]
        )

    def test_no_actor_level_clamp_or_outside_native_domain(self):
        casting, effects = self.fixture()
        for level in (248, 0, -1, True, 245.0):
            with self.assertRaises(ValueError):
                native_ally_scene_roots(8368, level, casting, effects)

    def test_missing_native_245_sample_fails_closed(self):
        casting, effects = self.fixture()
        casting["8368"]["levels"] = casting["8368"]["levels"][:200]
        with self.assertRaises(ValueError):
            native_ally_scene_roots(8368, 245, casting, effects)

    def test_effect_tree_rows_are_not_native_casting_triples(self):
        casting, effects = self.fixture()
        casting["8368"]["levels"][244] = {"duration": -1, "effects": [392568]}
        with self.assertRaises(ValueError):
            native_ally_scene_roots(8368, 245, casting, effects)

    def test_missing_root_definition_fails_closed(self):
        casting, effects = self.fixture()
        with self.assertRaises(ValueError):
            native_ally_scene_roots(8368, 245, casting, {})


if __name__ == "__main__":
    unittest.main()
