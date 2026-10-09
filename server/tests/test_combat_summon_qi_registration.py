import unittest
from types import SimpleNamespace

from wakfu_server.combat_summon_creation import register_fresh_summon_obstacle
from wakfu_server.combat_qi_registry import NativeQIRegistry


class NativeSummonQIRegistrationTests(unittest.TestCase):
    def actor(self, identity, slot=None):
        return SimpleNamespace(
            id=identity,
            native_obstacle_id=slot,
            position=(1, 1, 0),
            physical_radius=0,
            hp=10,
            native_carrier_id=None,
            native_carried_actor_id=None,
        )

    def fight(self):
        return SimpleNamespace(actors={7: self.actor(7, 0)}, native_effect_areas={})

    def test_faw_slot_is_not_reused_by_fresh_summon(self):
        fight = self.fight()
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        slots = [None] * 127
        slots[0] = dict(
            identity=["actor", 7],
            position=[1, 1],
            radius=0,
            indexed=True,
            movement_blocking=True,
        )
        slots[1] = dict(
            identity=["effect_area", 90],
            position=[2, 2],
            radius=0,
            indexed=True,
            movement_blocking=False,
        )
        fight.native_effect_areas[90] = dict(
            native_area_contract="faW",
            native_obstacle_id=1,
            cell=(2, 2, 0),
            native_faw_constructor=dict(obstacle=True),
        )
        registry = NativeQIRegistry(fight.native_qi_snapshot, slots)
        fight.native_qi_slots = registry.serialized_slots()
        fight.native_qi_touched_cells = registry.serialized_cells()
        created = self.actor(8)
        register_fresh_summon_obstacle(fight, created)
        self.assertEqual(created.native_obstacle_id, 2)
        self.assertEqual(fight.native_qi_slots[1]["identity"], ["effect_area", 90])
        self.assertEqual(fight.native_qi_slots[2]["identity"], ["actor", 8])
        self.assertNotIn(8, fight.actors)  # Actual roster registration follows.
        snapshot = NativeQIRegistry(
            fight.native_qi_snapshot,
            fight.native_qi_slots,
            touched_cells=fight.native_qi_touched_cells,
        ).snapshot()
        self.assertEqual(snapshot.U(1, 1), frozenset((0, 2)))

    def test_unknown_shared_population_rejects_registered_faw(self):
        fight = self.fight()
        fight.native_effect_areas[90] = dict(
            native_area_contract="faW", native_obstacle_id=1
        )
        created = self.actor(8)
        with self.assertRaisesRegex(ValueError, "shared native QI"):
            register_fresh_summon_obstacle(fight, created)
        self.assertIsNone(created.native_obstacle_id)

    def test_legacy_route_allows_only_proven_non_obstacle_areas(self):
        fight = self.fight()
        fight.native_effect_areas[90] = dict(
            native_area_contract="faX", native_obstacle_id=-1
        )
        created = self.actor(8)
        register_fresh_summon_obstacle(fight, created)
        self.assertEqual(created.native_obstacle_id, 1)
        self.assertFalse(hasattr(fight, "native_qi_slots"))

    def test_stale_actor_population_is_not_rebuilt(self):
        fight = self.fight()
        fight.native_qi_snapshot = dict(
            x=0, y=0, width=4, height=4, cell_masks=[0] * 16
        )
        fight.native_qi_slots = [None] * 127
        fight.native_qi_touched_cells = []
        with self.assertRaisesRegex(ValueError, "changed without registration"):
            register_fresh_summon_obstacle(fight, self.actor(8))


if __name__ == "__main__":
    unittest.main()
