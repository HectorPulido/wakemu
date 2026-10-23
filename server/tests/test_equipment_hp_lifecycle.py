import unittest

from wakfu_server.equipment_hp_lifecycle import NativeHPActor, OwnedEwoHPReplay
from wakfu_server.health_policy import visible


def _operation(uid, amount, index=0, *, restore=True, slot=4):
    return {
        "source_uid": uid,
        "slot": slot,
        "effect_index": index,
        "amount": amount,
        "definition_type": 0,
        "restore_current": restore,
        "reduce_current": True,
    }


class EquipmentHpLifecycleTests(unittest.TestCase):
    def test_production_flat_import_owns_lifecycle_types(self):
        self.assertEqual(
            NativeHPActor.__module__, "wakfu_server.equipment_hp_lifecycle"
        )

    def test_native_apply_remove_and_no_restore_wound(self):
        replay = OwnedEwoHPReplay(NativeHPActor(500, 1000))
        replay.apply(_operation(11, 50))
        self.assertEqual((replay.actor.hp, replay.actor.max_hp), (450, 950))
        replay.remove(11)
        self.assertEqual((replay.actor.hp, replay.actor.max_hp), (500, 1000))

        replay.apply(_operation(12, 50, restore=False))
        replay.remove(12)
        self.assertEqual((replay.actor.hp, replay.actor.max_hp), (450, 1000))

    def test_checkpoint_and_ordered_rebase_replay(self):
        replay = OwnedEwoHPReplay(NativeHPActor(900, 1000))
        replay.reconcile([_operation(21, 30, 0), _operation(22, 50, 1)])
        resumed = OwnedEwoHPReplay.restore(replay.checkpoint())
        self.assertEqual(resumed.plain_receipts(), replay.plain_receipts())

        stripped = OwnedEwoHPReplay.restore(resumed.checkpoint())
        for key in sorted(
            tuple(stripped.receipts),
            key=lambda item: (stripped._order(stripped.receipts[item]), item),
            reverse=True,
        ):
            stripped.remove(key)
        rebased = OwnedEwoHPReplay(
            NativeHPActor(
                1100,
                1200,
                stripped.actor.effect_base_minima[1],
                stripped.actor.effect_percentages[1],
                1 in stripped.actor.effect_frozen,
            )
        )
        rebased.reconcile([_operation(21, 30, 0), _operation(22, 50, 1)])
        self.assertEqual((rebased.actor.hp, rebased.actor.max_hp), (1020, 1120))

    def test_zero_native_current_stays_distinct_from_death(self):
        replay = OwnedEwoHPReplay(NativeHPActor(0, 10))
        replay.apply(_operation(31, 10))
        self.assertEqual((replay.actor.hp, replay.actor.max_hp), (0, 1))
        self.assertEqual(visible(100, 100, False), 1)
        self.assertEqual(visible(100, 100, False, True), 0)
        self.assertEqual(visible(100, 100, True), 0)


if __name__ == "__main__":
    unittest.main()
