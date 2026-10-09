"""Fresh registration validates actual QI ownership after a native slot release."""
from types import SimpleNamespace
import unittest
from wakfu_server.combat_summon import fresh_summon_slot_owned
from wakfu_server.combat_qi_registry import NativeQIRegistry


class SummonSlotReuseTests(unittest.TestCase):
    def test_released_slot_is_owned_by_new_qk_despite_retained_actor_identity(self):
        arena = dict(x=0, y=0, width=4, height=4, cell_masks=[0] * 16)
        registry = NativeQIRegistry(arena, [None] * 127)
        old = dict(
            identity=["actor", 232],
            position=[1, 1],
            radius=0,
            indexed=False,
            movement_blocking=True,
        )
        slot = registry.register(old)
        actor = SimpleNamespace(
            id=300, native_obstacle_id=slot, position=(1, 1, 0), physical_radius=0
        )
        preview = SimpleNamespace(
            native_qi_snapshot=arena,
            native_qi_slots=registry.serialized_slots(),
            actors={232: SimpleNamespace(native_obstacle_id=slot)},
        )
        # Before actual QI.g release the old QK still owns the byte.
        self.assertFalse(fresh_summon_slot_owned(preview, actor))
        registry.remove(slot, ("actor", 232))
        new = dict(old, identity=["actor", 300])
        self.assertEqual(registry.register(new), slot)
        actor = SimpleNamespace(
            id=300, native_obstacle_id=slot, position=(1, 1, 0), physical_radius=0
        )
        preview = SimpleNamespace(
            native_qi_snapshot=arena,
            native_qi_slots=registry.serialized_slots(),
            actors={232: SimpleNamespace(native_obstacle_id=slot)},
        )
        self.assertTrue(fresh_summon_slot_owned(preview, actor))
        actor.id = 301
        self.assertFalse(fresh_summon_slot_owned(preview, actor))
        actor.id = 300
        actor.position = (2, 1, 0)
        self.assertFalse(fresh_summon_slot_owned(preview, actor))
