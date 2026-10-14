import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from native_scene_geometry_priority import (
    native_identity_spare_priority,
    zero_range_hostile_scene_priority,
)
from resource_priority_scheduler import PreparationScheduler, SceneWork


class NativeSceneGeometryPriorityTests(unittest.TestCase):
    def test_source_discovered_npc_target_prefers_side_player_off_blocking_line(self):
        scenario = dict(
            kind="native_opponent",
            discovery="positive_native_target_identity_v1",
            opponent={"reference": 4152, "level": 100},
        )
        source, target = (-8, -7, -1), (-10, -7, -1)
        candidates = [(-9, -7, -1), (-8, -8, -1)]
        ordered = sorted(
            candidates,
            key=lambda cell: (
                native_identity_spare_priority(scenario, source, target, cell),
                cell,
            ),
        )
        self.assertEqual(ordered, [(-8, -8, -1), (-9, -7, -1)])
        self.assertEqual(
            native_identity_spare_priority(scenario, target, source, (-9, -7, -1)), 1
        )

    def test_unrelated_ally_and_owned_preparation_scenes_retain_original_order(self):
        for scenario in (
            None,
            {},
            dict(kind="native_opponent", discovery="ordinary_same_species_ally_v1"),
            dict(
                kind="native_opponent",
                discovery="positive_native_target_identity_v1",
                opponent={"team": 1},
            ),
        ):
            self.assertEqual(
                native_identity_spare_priority(
                    scenario, (-8, -7, -1), (-10, -7, -1), (-9, -7, -1)
                ),
                0,
            )

    def test_valid_replacement_preempts_colliding_scene_and_preserves_resume_identity(
        self,
    ):
        invalid, valid, other = (
            ("ordinary", (0, 0, 0)),
            ("ordinary", (2, 0, 0)),
            ("other", (3, 0, 0)),
        )
        scheduler = PreparationScheduler([invalid, other, valid])
        resume = SceneWork(valid, object(), ((2, 0, 0),), {"other_actor": 1})
        scheduler.pending[-1] = resume
        scheduler.prioritize_scenes([valid, valid])
        works = list(scheduler)
        self.assertIs(works[0], resume)
        self.assertEqual([w.scene for w in works], [valid, invalid, other])
        self.assertTrue(works[0].resumed)

    def test_actual_zero_range_hostile_circle_precedes_optional_overlapping_ally(self):
        root = dict(
            effect_class=3,
            criteria="",
            area_class="anu",
            area_native="circle-3",
            native_target_selector={"class": "fcE", "mask": 9},
        )
        prerequisite = {"kind": "owned_spell_sequence"}
        ally = {"discovery": "ordinary_same_species_ally_v1"}
        scenes = [prerequisite, ally, None]
        self.assertEqual(
            zero_range_hostile_scene_priority(scenes, [root], 0, 0),
            [prerequisite, None, ally],
        )
        self.assertEqual(scenes, [prerequisite, ally, None])
        for changed in (
            {"criteria": 'HasState(1,"caster")'},
            {"native_target_selector": {"class": "fcE", "mask": 129}},
            {"area_class": "unknown", "area_native": None},
        ):
            self.assertEqual(
                zero_range_hostile_scene_priority(
                    scenes, [dict(root, **changed)], 0, 0
                ),
                scenes,
            )
        self.assertEqual(
            zero_range_hostile_scene_priority(scenes, [root], 1, 2), scenes
        )

    def test_native_circle_and_ring_expand_recipient_envelope_without_cast_range_change(
        self,
    ):
        from monster_pending_scenarios import effect_search_envelope

        effects = {
            "1": {"area_class": "anu", "area_native": "circle-3", "children": []},
            "2": {"area_class": "anH", "area_native": "ring-4-5", "children": []},
        }
        self.assertEqual(effect_search_envelope(effects, [1, 2], 0), 5)
        self.assertEqual(effect_search_envelope(effects, [1], 2), 5)
        self.assertEqual(
            effect_search_envelope(
                {"3": {"area_class": "unknown", "children": []}}, [3], 0
            ),
            0,
        )
        self.assertEqual(effect_search_envelope(effects, [1, 2], 10), 12)
