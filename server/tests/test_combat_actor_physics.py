"""Fresh physics authority persists through actual coordinate updates."""
import unittest
from types import SimpleNamespace

from wakfu_server.combat_actor_snapshot import ActorSnapshot
from wakfu_server.combat_qi_fight import move_registered_actor
from wakfu_server.combat_state import Actor


class NativeActorPhysicsTests(unittest.TestCase):
    def snapshot(self, actor, **changes):
        fields = dict(
            actor_id=actor.id,
            stats={1: actor.hp, 2: actor.ap, 3: actor.mp, 35: actor.initiative},
            minima={1: 0, 2: 0, 3: 0},
            maxima={1: actor.max_hp, 2: actor.max_ap, 3: actor.max_mp},
            frozen=frozenset(),
            physical_radius=0,
            provenance="native eGj boundary",
            native_los_height=0,
            native_physical_position=actor.position,
            native_jump_height=4,
        )
        fields.update(changes)
        return ActorSnapshot(**fields)

    def test_install_and_coordinate_update_preserve_actual_physics(self):
        actor = Actor(1, 0, (2, 3, 0), 20, 6, 3, 10, 20)
        self.snapshot(actor).install(actor)
        self.assertEqual(actor.native_jump_height, 4)
        self.assertEqual(actor.native_physical_position, (2, 3, 0))
        move_registered_actor(SimpleNamespace(native_qi_slots=None), actor, (4, 5, 1))
        self.assertEqual(actor.native_physical_position, actor.position)

    def test_unknown_physics_is_not_inferred_by_coordinate_update(self):
        actor = Actor(1, 0, (2, 3, 0), 20, 6, 3, 10, 20)
        move_registered_actor(SimpleNamespace(native_qi_slots=None), actor, (4, 5, 1))
        self.assertIsNone(actor.native_physical_position)
        self.assertIsNone(actor.native_jump_height)

    def test_changed_or_missing_fresh_physics_rejects_before_install(self):
        for changes in (
            {"native_physical_position": None},
            {"native_physical_position": (3, 3, 0)},
            {"native_jump_height": None},
            {"native_jump_height": 0},
        ):
            actor = Actor(1, 0, (2, 3, 0), 20, 6, 3, 10, 20)
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                self.snapshot(actor, **changes).install(actor)
            self.assertIsNone(actor.effect_stats)
            self.assertIsNone(actor.native_physical_position)
