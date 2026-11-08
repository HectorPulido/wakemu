"""Reinforcements cannot spawn across a physically blocked native corridor."""
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server.rift_reinforcement_placement import select_positions


class RiftReinforcementReachabilityTests(unittest.TestCase):
    def test_static_masks_and_registered_obstacles_bound_reachable_population(self):
        cells = {(x, 0, 0) for x in range(6)}
        player = SimpleNamespace(id=1, team=0, position=(0, 0, 0))
        fight = SimpleNamespace(
            walkable=cells,
            edges={(a, b) for a in cells for b in cells if abs(a[0] - b[0]) == 1},
            actors={1: player},
            _in_play=lambda actor: True,
            rift_wave_state={"catalog": {"wave_id": 1}},
        )
        for barrier in ("mask", "obstacle"):
            with self.subTest(barrier=barrier):
                qi = SimpleNamespace(
                    x=0,
                    y=0,
                    width=6,
                    height=1,
                    masks=[0, 0, 256 if barrier == "mask" else 0, 0, 0, 0],
                    aK=lambda x, y: 0 <= x < 6 and y == 0,
                )

                def population(x, y):
                    return (0,) if x == 0 or (x == 2 and barrier == "obstacle") else ()

                with (
                    patch(
                        "wakfu_server.combat_encounter_roles.assigned_roles",
                        return_value=SimpleNamespace(player_team=0),
                    ),
                    patch(
                        "wakfu_server.combat_qi_fight.current_registry",
                        return_value=object(),
                    ),
                    patch(
                        "wakfu_server.combat_pointer_qi_registry.registered_population",
                        return_value=(qi, population),
                    ),
                    patch(
                        "wakfu_server.combat_pointer_qi_registry.registered_obstacle",
                        return_value={"movement_blocking": True},
                    ),
                    patch(
                        "wakfu_server.combat_actor_snapshot.native_actor_catalog",
                        return_value={"npc_profiles": {"1": {"physical_radius": 0}}},
                    ),
                ):
                    for seed in ("a", "b", "c"):
                        self.assertEqual(
                            select_positions(fight, references=(1,), seed=seed, wave=2),
                            ((1, 0, 0),),
                        )
                    with self.assertRaisesRegex(
                        ValueError, "physically free reachable"
                    ):
                        select_positions(fight, references=(1, 1), seed="a", wave=2)
