import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest

from wakfu_server.dungeon_stage_levels import MODE, prepare_policy, selector
from wakfu_server.dungeon_runtime_config import prepare_configuration


def config(orders=(1, 2, 3), low=8, high=12):
    return dict(
        provenance="Test explicit server policy",
        level_policy=dict(mode=MODE, optional_mode="native_maximum", provenance="Test"),
        topology=dict(rooms=[dict(order=n) for n in orders]),
        compiled_plan=dict(
            rooms=[
                dict(
                    order=n,
                    monsters=[
                        dict(
                            ref_id=1,
                            count=1,
                            native_min_level=low,
                            native_max_level=high,
                        )
                    ],
                )
                for n in orders
            ]
        ),
    )


def grade(cfg, order, low=8, high=12):
    row = dict(min_level=low, max_level=high)
    return selector(cfg, room_order=order)(row, row)


class StageLevelsTests(unittest.TestCase):
    def test_same_species_rises_with_native_bounds(self):
        self.assertEqual([grade(config(), n) for n in (1, 2, 3)], [8, 10, 12])

    def test_legacy_pins_remain_minimum_without_room_context(self):
        cfg = config()
        cfg["level_policy"] = dict(mode="native_minimum", provenance="Legacy")
        self.assertEqual(grade(cfg, None), 8)

    def test_single_room_and_fixed_levels_do_not_invent_extra_grades(self):
        self.assertEqual(grade(config((1,)), 1), 8)
        self.assertEqual(
            [grade(config(low=9, high=9), n, 9, 9) for n in (1, 2, 3)], [9, 9, 9]
        )
        self.assertEqual(
            [grade(config((1, 2, 3, 4), low=8, high=9), n, 8, 9) for n in (1, 2, 3, 4)],
            [8, 8, 8, 9],
        )

    def test_optional_does_not_change_three_main_stage_fractions(self):
        cfg = config((1, 2, 3, 4))
        cfg["topology"]["optional_room_policy"] = dict(
            policy="reviewed-main-and-optional-rooms-v1",
            main_room_orders=[1, 2, 3],
            source_evidence="Native",
            optional_rooms=[
                dict(
                    order=4,
                    source_order=4,
                    access=dict(status="unresolved_native_access", evidence="Native"),
                )
            ],
        )
        self.assertEqual([grade(cfg, n) for n in (1, 2, 3, 4)], [8, 10, 12, 12])

    def test_selected_branch_counts_logical_stages_once(self):
        cfg = config()
        cfg["topology"]["branch_routes"] = [
            dict(key="a", rooms=[dict(order=n) for n in (1, 2, 3)]),
            dict(key="b", rooms=[dict(order=n) for n in (1, 2, 3)]),
        ]
        cfg["topology"]["selected_branch"] = "b"
        self.assertEqual([grade(cfg, n) for n in (1, 2, 3)], [8, 10, 12])

    def test_bad_room_and_native_bounds_fail_closed(self):
        for n in (None, True, 0, 4):
            with self.assertRaises(ValueError):
                grade(config(), n)
        with self.assertRaises(ValueError):
            selector(config(), room_order=1)(
                dict(min_level=9, max_level=12), dict(min_level=8, max_level=12)
            )
        with self.assertRaises(ValueError):
            prepare_policy(
                dict(mode=MODE, provenance="X", optional_mode="invent_level"),
                provenance="X",
            )

    def test_real_rosters_and_rounding_composition_exceptions_have_ascending_means(
        self,
    ):
        active = json.loads(
            (
                Path(__file__).parent / "fixtures/dungeon_stage_level_samples.json"
            ).read_text()
        )
        for key in (
            "native_dungeon_27",
            "native_dungeon_185",
            "native_dungeon_140",
            "native_dungeon_153",
        ):
            cfg = config(tuple(r["order"] for r in active[key]))
            cfg["compiled_plan"]["rooms"] = copy.deepcopy(active[key])
            cfg["level_policy"] = config()["level_policy"]
            means = []
            for room in cfg["compiled_plan"]["rooms"]:
                total = sum(
                    m["count"]
                    * grade(
                        cfg, room["order"], m["native_min_level"], m["native_max_level"]
                    )
                    for m in room["monsters"]
                )
                means.append(total / sum(m["count"] for m in room["monsters"]))
            self.assertTrue(all(a < b for a, b in zip(means, means[1:])), (key, means))

    def test_impossible_fixed_grade_composition_requires_review(self):
        cfg = config((1, 2))
        cfg["compiled_plan"]["rooms"][0]["monsters"][0].update(
            native_min_level=10, native_max_level=10
        )
        cfg["compiled_plan"]["rooms"][1]["monsters"][0].update(
            native_min_level=9, native_max_level=9
        )
        with self.assertRaisesRegex(ValueError, "review room composition"):
            grade(cfg, 1, 10, 10)


if __name__ == "__main__":
    unittest.main()
