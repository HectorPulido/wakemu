"""Artifact free-cell scans honor current native fighter lifecycle."""
import unittest
from unittest.mock import patch

from wakfu_server.combat_state import Actor, Fight
from wakfu_server.combat_global_pv_collections import (
    initialize_global_pv_collections,
    set_global_fighter_status,
)
from wakfu_server.rift_artifact_generation import _reachable_free_cells


class RiftArtifactReachabilityTests(unittest.TestCase):
    def test_retired_cells_are_free_and_reactivated_cells_are_occupied(self):
        cells = {(x, 0, 0) for x in range(5)}
        player = Actor(1, 0, (0, 0, 0), 100, 6, 6, 10, 10)
        enemy = Actor(-1, 1, (2, 0, 0), 100, 6, 6, 10, 10)
        fight = Fight(
            99, [player, enemy], cells, {0: {player.position}, 1: {enemy.position}}
        )
        initialize_global_pv_collections(fight, tuple(fight.actors))
        fight.native_effect_areas = {7: {"cell": (4, 0, 0)}}
        with patch(
            "wakfu_server.combat_qi_movement.movement_blocked_cells", return_value=set()
        ):
            for status in ("OFF_PLAY", "OUT_OF_PLAY", "IN_PLAY"):
                with self.subTest(status=status):
                    set_global_fighter_status(fight, enemy.id, status)
                    expected = {(1, 0, 0), (3, 0, 0)}
                    if status != "IN_PLAY":
                        expected.add(enemy.position)
                    self.assertEqual(
                        set(_reachable_free_cells(fight, player)), expected
                    )
        self.assertEqual(set(fight.actors), {1, -1})
