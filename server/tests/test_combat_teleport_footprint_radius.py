"""Native QI teleport occupancy over registered actor footprints."""
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from wakfu_server.combat_displacement import NativeDisplacementHandler


class DisplacementAuthority:
    def __init__(self, *, carried=False, carrying=False):
        self.carried, self.carrying = carried, carrying

    def __call__(self, fight, actor):
        return SimpleNamespace(
            is_carried=self.carried,
            is_carrying=self.carrying,
            targeting={"baF": False, "baG": False, "baK": False},
        )

    def properties(self, fight, actor):
        return frozenset()


class TeleportFootprintTests(unittest.TestCase):
    def setUp(self):
        self.actor = SimpleNamespace(
            id=7,
            team=0,
            hp=10,
            position=(2, 2, 0),
            physical_radius=1,
            native_obstacle_id=0,
        )
        slots = [None] * 127
        slots[0] = dict(
            identity=["actor", 7],
            position=[2, 2],
            radius=1,
            indexed=True,
            movement_blocking=True,
        )
        self.fight = SimpleNamespace(
            id=1,
            phase="active",
            current=7,
            actors={7: self.actor},
            native_effect_areas={},
            native_retired_area_managers={},
            native_carry_pairs={},
            native_qi_snapshot=dict(x=0, y=0, width=5, height=5, cell_masks=[0] * 25),
            native_qi_slots=slots,
            native_qi_touched_cells=[],
            native_qi_byte_topology=None,
            native_qi_movement_override=False,
            native_qi_ignored_slots=[],
        )
        self.handler = NativeDisplacementHandler(
            self.fight,
            [],
            action_id=1,
            allocate_uid=lambda: 50,
            authority=DisplacementAuthority(),
            selected_surface=lambda *_: object(),
        )

    def add_actor_blocker(self, slot=1, *, position=(3, 3)):
        blocker = SimpleNamespace(
            id=8,
            team=1,
            hp=10,
            position=(*position, 0),
            physical_radius=0,
            native_obstacle_id=slot,
        )
        self.fight.actors[8] = blocker
        self.fight.native_qi_slots[slot] = dict(
            identity=["actor", 8],
            position=list(position),
            radius=0,
            indexed=True,
            movement_blocking=True,
        )
        return blocker

    def test_radius_one_empty_footprint_allows_existing_self_overlap(self):
        self.assertTrue(self.handler._teleport_free(self.actor, (2, 2, 0)))

    def test_off_center_actor_and_area_qk_blockers_reject(self):
        self.add_actor_blocker()
        self.assertFalse(self.handler._teleport_free(self.actor, (2, 2, 0)))

        self.setUp()
        self.fight.native_effect_areas[91] = dict(
            uid=91,
            reference=1034,
            cell=(3, 3, 0),
            native_area_contract="faW",
            native_obstacle_id=1,
            native_faw_constructor={"obstacle": True},
        )
        self.fight.native_qi_slots[1] = dict(
            identity=["effect_area", 91],
            position=[3, 3],
            radius=0,
            indexed=True,
            movement_blocking=True,
        )
        self.assertFalse(self.handler._teleport_free(self.actor, (2, 2, 0)))

    def test_off_center_terrain_mask_rejects_even_under_movement_override(self):
        self.fight.native_qi_snapshot["cell_masks"][3 * 5 + 3] = 768
        self.fight.native_qi_movement_override = True
        self.assertFalse(self.handler._teleport_free(self.actor, (2, 2, 0)))

    def test_ignored_slots_and_override_skip_actor_occupancy(self):
        self.add_actor_blocker()
        self.fight.native_qi_ignored_slots = [1]
        self.assertTrue(self.handler._teleport_free(self.actor, (2, 2, 0)))
        self.fight.native_qi_ignored_slots = []
        self.fight.native_qi_movement_override = True
        self.assertTrue(self.handler._teleport_free(self.actor, (2, 2, 0)))

    def test_radius_zero_teleport_footprint_remains_supported(self):
        self.actor.physical_radius = 0
        self.fight.native_qi_slots[0]["radius"] = 0
        self.assertTrue(self.handler._teleport_free(self.actor, (3, 2, 0)))

    def test_accepted_teleport_reaches_radius_scan_but_keeps_life_and_carry_guards(
        self,
    ):
        source = SimpleNamespace(id=9, team=1)
        geometry = dict(
            actor=self.actor, destination=(2, 2, 0), force=False, check_cells=True
        )
        with patch.object(
            self.handler, "_teleport_free", wraps=self.handler._teleport_free
        ) as scan:
            self.assertTrue(self.handler._teleport_accepted(geometry, source, set()))
            scan.assert_called_once_with(self.actor, (2, 2, 0))

        self.actor.hp = 0
        with patch.object(
            self.handler,
            "_teleport_free",
            side_effect=AssertionError("scan must not run"),
        ):
            with self.assertRaisesRegex(ValueError, "ordinary radius0 actor"):
                self.handler._teleport_accepted(geometry, source, set())

        self.actor.hp = 10
        self.handler.authority = DisplacementAuthority(carried=True)
        with patch.object(
            self.handler,
            "_teleport_free",
            side_effect=AssertionError("scan must not run"),
        ):
            with self.assertRaisesRegex(ValueError, "ordinary radius0 actor"):
                self.handler._teleport_accepted(geometry, source, set())


if __name__ == "__main__":
    unittest.main()
