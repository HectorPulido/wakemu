"""Coordinate planning preserves the actual actor/QI population contract."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace
import unittest

from test_ombrage_native_paid_clock import back_path
from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_supreme_scene_policies import reconstructed_ombrage_scene


class OmbrageNativePlanningTests(unittest.TestCase):
    def test_joint_casting_goal_preserves_actual_qi_and_real_movement_budget(self):
        root = Path(__file__).resolve().parents[2]
        scene = reconstructed_ombrage_scene(
            json.loads(
                (root / ".runtime/ultimate-scenes-20261021/map-1229.json").read_text()
            )
        )
        actors = [
            Actor(i, 0, cell, 100, 10, 7, 0, 200, i, True)
            for i, cell in enumerate(scene["party_placement_cells"], 1)
        ]
        actors.append(Actor(-200, 1, scene["source"], 100, 0, 0, 0, 200, direction=3))
        fight = Fight(
            99,
            actors,
            scene["cells"],
            {0: set(scene["party_placement_cells"]), 1: {scene["source"]}},
            scene["edges"],
        )
        fight.native_qi_snapshot = dict(
            x=-7,
            y=-7,
            width=15,
            height=15,
            cell_masks=[
                0 if (x, y, 0) in scene["cells"] else 256
                for y in range(-7, 8)
                for x in range(-7, 8)
            ],
        )
        for slot, actor in enumerate(actors):
            actor.native_obstacle_id = slot
            actor.physical_radius = 0
            actor.native_los_height = 12 if actor.id == -200 else 2
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight, physical_radii={actor.id: 0 for actor in actors}
            ),
        )
        fight.phase, fight.order, fight.turn_index = (
            "active",
            [2, 4, 1, 6, 3, 5, -200],
            0,
        )
        fight.native_qi_visibility_ignored_slots = ()
        authority = SimpleNamespace(properties=lambda fight, actor: frozenset())
        before = deepcopy(
            (
                fight.native_qi_slots,
                fight.native_qi_touched_cells,
                {identity: actor.position for identity, actor in fight.actors.items()},
            )
        )

        def preserves_back(cell, approach):
            return (
                back_path(
                    fight,
                    2,
                    require_back=True,
                    maximum_range=1,
                    require_los=True,
                    actor_authority=authority,
                    origin=cell,
                    movement_prefix=approach,
                )
                is not None
            )

        path = back_path(
            fight,
            2,
            require_back=False,
            maximum_range=3,
            require_los=True,
            actor_authority=authority,
            require_linear=True,
            goal_predicate=preserves_back,
        )
        self.assertIsNotNone(path)
        followup = back_path(
            fight,
            2,
            require_back=True,
            maximum_range=1,
            require_los=True,
            actor_authority=authority,
            origin=path[-1],
            movement_prefix=path,
        )
        self.assertIsNotNone(followup)
        self.assertLessEqual(len(path) + len(followup), fight.actors[2].mp)
        self.assertEqual(
            before,
            (
                fight.native_qi_slots,
                fight.native_qi_touched_cells,
                {identity: actor.position for identity, actor in fight.actors.items()},
            ),
        )
        current_registry(fight)
        stale = deepcopy(fight)
        stale.actors[2].position = path[-1]
        with self.assertRaisesRegex(ValueError, "actual lifecycle update"):
            current_registry(stale)
