import unittest
import sys
from unittest.mock import patch

from wakfu_server.combat_global_pv_collections import initialize_global_pv_collections
from wakfu_server.combat_qi_fight import (
    current_registry,
    install_fresh_actor_slots,
    move_registered_actor,
    prepare_fresh_actor_slots,
)
from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_trove_long_map import NativeTroveLongMap
from wakfu_server.combat_geometry_snapshot import source_snapshot


class CurrentRegistryPVViewTests(unittest.TestCase):
    def _fight(self, count=6):
        actors = [
            Actor(
                100 + index if index % 2 == 0 else -100 - index,
                index % 2,
                (index, 0, 0),
                20,
                6,
                3,
                10 - index,
                10,
                owner_id=(1000 + index if index % 2 == 0 else None),
                controlled=index % 2 == 0,
            )
            for index in range(count)
        ]
        for actor in actors:
            actor.physical_radius = 0
        walkable = {(index, 0, 0) for index in range(count + 1)}
        fight = Fight(
            992,
            actors,
            walkable,
            {
                team: {actor.position for actor in actors if actor.team == team}
                for team in (0, 1)
            },
        )
        fight.native_qi_snapshot = {
            "x": 0,
            "y": 0,
            "width": count + 1,
            "height": 1,
            "cell_masks": [0] * (count + 1),
        }
        initialize_global_pv_collections(fight, tuple(fight.actors))
        install_fresh_actor_slots(
            fight,
            prepare_fresh_actor_slots(
                fight,
                physical_radii={actor.id: 0 for actor in fight.actors.values()},
            ),
        )
        return fight

    def _count_registry_builds(self, fight, *, force_fallback=False):
        calls = []
        original_code = NativeTroveLongMap.__init__.__code__
        previous_profile = sys.getprofile()

        def observe(frame, event, arg):
            if event == "call" and frame.f_code is original_code:
                calls.append(1)

        try:
            sys.setprofile(observe)
            if force_fallback:
                with patch(
                    "wakfu_server.combat_qi_fight._current_registry_pv_view_allowed",
                    return_value=False,
                ):
                    registry = current_registry(fight)
            else:
                registry = current_registry(fight)
        finally:
            sys.setprofile(previous_profile)
        return registry, len(calls)

    def test_native_actor_loop_reuses_one_read_view_with_identical_registry(self):
        fight = self._fight()
        # Exercise the real move producer: moved rows store an exact tuple,
        # while untouched fresh-registration rows retain exact lists.
        moved = fight.actors[100]
        move_registered_actor(fight, moved, (6, 0, 0))
        self.assertIs(
            type(fight.native_qi_slots[moved.native_obstacle_id]["position"]), tuple
        )
        untouched = fight.actors[-101]
        self.assertIs(
            type(fight.native_qi_slots[untouched.native_obstacle_id]["position"]), list
        )
        before = source_snapshot(fight)
        optimized, builds = self._count_registry_builds(fight)
        self.assertEqual(builds, 1)
        optimized_state = (optimized.serialized_slots(), optimized.serialized_cells())
        self.assertEqual(source_snapshot(fight), before)

        baseline, baseline_builds = self._count_registry_builds(
            fight, force_fallback=True
        )
        self.assertEqual(baseline_builds, len(fight.actors))
        self.assertEqual(
            (baseline.serialized_slots(), baseline.serialized_cells()), optimized_state
        )
        self.assertEqual(source_snapshot(fight), before)

    def test_custom_carry_callback_keeps_fresh_guards_after_mutation(self):
        fight = self._fight()
        target = next(
            actor for actor in fight.actors.values() if actor.native_obstacle_id == 1
        )
        import wakfu_server.combat_carrying as carrying

        original = carrying.carrying_relations
        calls = []

        def mutate_fighter_status(current_fight, actor):
            calls.append(actor.id)
            if actor is not target:
                current_fight.native_global_pv_collections["fighter_status"][
                    str(target.id)
                ] = "OUT_OF_PLAY"
            return original(current_fight, actor)

        with patch.object(carrying, "carrying_relations", mutate_fighter_status):
            with self.assertRaisesRegex(ValueError, "out_of_play"):
                current_registry(fight)
        self.assertGreaterEqual(len(calls), 1)
        self.assertEqual(
            fight.native_global_pv_collections["fighter_status"][str(target.id)],
            "OUT_OF_PLAY",
        )


if __name__ == "__main__":
    unittest.main()
