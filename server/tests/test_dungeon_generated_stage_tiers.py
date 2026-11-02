import copy
import unittest

from wakfu_server.dungeon_local_roster_policy import draft, generated_reference


class GeneratedStageTierTests(unittest.TestCase):
    def setUp(self):
        self.catalog = {
            1: dict(
                ref=1,
                name="Higher",
                min_level=44,
                max_level=48,
                native_abilities=[dict(spell_id=549)],
            ),
            2: dict(
                ref=2,
                name="Middle",
                min_level=40,
                max_level=44,
                native_abilities=[dict(spell_id=549)],
            ),
            3: dict(
                ref=3,
                name="Lower",
                min_level=38,
                max_level=42,
                native_abilities=[dict(spell_id=549)],
            ),
        }

    def test_reference_order_does_not_reverse_new_anonymous_stage_tiers(self):
        selected = [
            generated_reference(
                [1, 2, 3], self.catalog, order=stage, room_count=3, index=0
            )
            for stage in (1, 2)
        ]
        self.assertEqual(selected, [3, 2])
        self.assertLess(
            self.catalog[selected[0]]["min_level"],
            self.catalog[selected[1]]["min_level"],
        )

    def test_final_species_and_empty_book_controller_assignment_are_unchanged(self):
        self.assertEqual(
            generated_reference(
                [1, 2, 3], self.catalog, order=3, room_count=3, index=0
            ),
            3,
        )
        controller = dict(
            ref=4, name="Controller", min_level=99, max_level=99, native_abilities=[]
        )
        self.catalog[4] = controller
        self.assertEqual(
            generated_reference(
                [1, 2, 3, 4], self.catalog, order=1, room_count=3, index=3
            ),
            4,
        )
        self.assertEqual(
            generated_reference(
                [1, 2, 3, 4], self.catalog, order=1, room_count=3, index=0
            ),
            3,
        )

    def test_real_draft_preserves_known_counts_boss_and_original_source(self):
        native = list(self.catalog.values())
        boss = dict(
            ref=9,
            name="Boss",
            min_level=53,
            max_level=58,
            native_abilities=[dict(spell_id=549)],
        )
        native.append(boss)
        policy = dict(
            schema="native-npc-activation-v1",
            enabled_monsters={
                str(n["ref"]): dict(min_level=1, max_level=32767, spell_ids=[549])
                for n in native
            },
        )
        anonymous = lambda order: dict(
            order=order,
            diagnostics=["unresolved_identity"],
            monsters=[
                dict(
                    ref_id=None, name="Random monster species", count=7, role="monster"
                )
            ],
        )
        last = dict(
            order=3,
            diagnostics=[],
            monsters=[
                dict(ref_id=9, name="Boss", count=1, role="boss"),
                dict(ref_id=1, name="Higher", count=7, role="monster"),
            ],
        )
        plan = dict(
            definition_id=25, slug="review", rooms=[anonymous(1), anonymous(2), last]
        )
        original = copy.deepcopy(plan)
        result = draft(
            plan,
            dict(id=25, raw_cno=[1, 2, 3, 9]),
            native,
            admission_policy=policy,
            boss_references=(9,),
        )
        self.assertEqual(
            [
                (r["monsters"][0]["ref_id"], r["monsters"][0]["count"])
                for r in result["rooms"][:2]
            ],
            [(3, 7), (2, 7)],
        )
        self.assertEqual(result["rooms"][2]["monsters"], last["monsters"])
        self.assertEqual(plan, original)
        self.assertFalse(result["official"])
        self.assertTrue(
            result["generated_species_assignment_policy"][
                "requires_recipe_review_before_activation"
            ]
        )

    def test_fixed_tier_rotation_is_deterministic_under_catalog_order(self):
        self.catalog[5] = dict(self.catalog[3], ref=5)
        expected = [
            generated_reference(
                [1, 2, 3, 5], self.catalog, order=1, room_count=3, index=i
            )
            for i in range(4)
        ]
        self.assertEqual(expected, [3, 5, 3, 5])
        self.assertEqual(
            expected,
            [
                generated_reference(
                    [5, 3, 2, 1], self.catalog, order=1, room_count=3, index=i
                )
                for i in range(4)
            ],
        )
