import unittest
from freecell_area_scene import rank_recipients, rank_anchors


class FreeCellAreaSceneTests(unittest.TestCase):
    def setUp(self):
        self.root = dict(
            effect_class=4,
            criteria="",
            area_class="anJ",
            native_area_points=[[0, 0], [1, 0], [2, 0], [3, 0]],
            native_target_selector=dict(class_="fcE"),
        )
        self.root["native_target_selector"] = {"class": "fcE", "mask": 9}
        self.casting = dict(free_cell=True)

    def test_forward_empty_anchor_prefers_far_recipient_over_adjacent(self):
        enemies = [(1, 0, 0), (2, 0, 0)]
        anchors = [(1, 0, 0)]
        self.assertEqual(
            rank_recipients(
                (0, 0, 0), enemies, anchors, [self.root], self.casting, 1, 1
            ),
            enemies[::-1],
        )
        self.assertEqual(
            set(enemies),
            set(
                rank_recipients(
                    (0, 0, 0), enemies, anchors, [self.root], self.casting, 1, 1
                )
            ),
        )

    def test_actual_anchor_orientation_is_preserved(self):
        anchors = [(0, 1, 0), (1, 0, 0)]
        self.assertEqual(
            rank_anchors((0, 0, 0), anchors, [(2, 0, 0)], [self.root], self.casting),
            anchors[::-1],
        )

    def test_conditional_ally_unknown_and_nonfreecell_keep_order(self):
        enemies = [(1, 0, 0), (2, 0, 0)]
        for changes in [
            dict(criteria='HasState(1, "caster")'),
            dict(native_target_selector={"class": "fcE", "mask": 5}),
            dict(area_class="unknown", native_area_points=None),
        ]:
            root = dict(self.root, **changes)
            self.assertEqual(
                rank_recipients(
                    (0, 0, 0), enemies, [(1, 0, 0)], [root], self.casting, 1, 1
                ),
                enemies,
            )
        self.assertEqual(
            rank_recipients((0, 0, 0), enemies, [(1, 0, 0)], [self.root], {}, 1, 1),
            enemies,
        )

    def test_linear_casting_constraint_does_not_allow_diagonal_anchor(self):
        enemies = [(2, 1, 0), (2, 0, 0)]
        self.assertEqual(
            rank_recipients(
                (0, 0, 0),
                enemies,
                [(1, 1, 0), (1, 0, 0)],
                [self.root],
                dict(free_cell=True, linear=True),
                1,
                2,
            ),
            enemies[::-1],
        )

    def test_optional_ally_does_not_occupy_only_productive_anchor_first(self):
        from freecell_area_scene import rank_scenarios

        prerequisite = dict(kind="owned_spell_sequence", actions=[1])
        ally = dict(discovery="ordinary_same_species_ally_v1")
        scenes = [prerequisite, ally, None]
        self.assertEqual(
            rank_scenarios(scenes, [self.root], self.casting),
            [prerequisite, None, ally],
        )
        self.assertEqual(scenes, [prerequisite, ally, None])
        self.assertEqual(rank_scenarios(scenes, [self.root], {}), scenes)

    def test_existing_native_selector_policy_includes_qk_and_mixed_relation_areas(self):
        enemies = [(1, 0, 0), (2, 0, 0)]
        for mask in (9 | (1 << 50), 1):
            root = dict(
                self.root, native_target_selector={"class": "fcE", "mask": mask}
            )
            self.assertEqual(
                rank_recipients(
                    (0, 0, 0), enemies, [(1, 0, 0)], [root], self.casting, 1, 1
                ),
                enemies[::-1],
            )
        unknown = dict(
            self.root, native_target_selector={"class": "fcE", "mask": 9 | (1 << 39)}
        )
        self.assertEqual(
            rank_recipients(
                (0, 0, 0), enemies, [(1, 0, 0)], [unknown], self.casting, 1, 1
            ),
            enemies,
        )
