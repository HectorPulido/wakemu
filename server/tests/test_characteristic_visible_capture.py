"""Receipt-backed retired presentation does not allocate unused snapshots."""
import struct
import unittest
from unittest.mock import patch
from test_combat_qi_death_lifecycle import NativeQIDeathLifecycleTests
from test_combat_characteristic_reconciliation import CharacteristicReconciliationTests
from wakfu_server import combat_characteristic_reconciliation as reconciliation
from wakfu_server.combat_ordinary_qi_retirement import complete_ordinary_qi_death
from wakfu_server.combat_global_pv_collections import (
    set_global_fighter_status,
    register_global_fighter,
)
from wakfu_server.combat_state import Actor
from wakfu_server.combat_wire import decode_actor_state


class VisibleCharacteristicCaptureTests(unittest.TestCase):
    def test_retired_maps_off_play_birth_custom_and_expiration(self):
        fight, player, retired, corpse = NativeQIDeathLifecycleTests().fight()
        fight.apply_effect_damage(player.id, retired.id, retired.hp)
        self.assertTrue(complete_ordinary_qi_death(fight, retired))
        for actor in fight.actors.values():
            for name in reconciliation._MAPS:
                if getattr(actor, name, None) is None:
                    setattr(actor, name, {7: 1})
        before = reconciliation._capture_characteristics(fight)
        public_before = reconciliation.characteristic_signatures(fight)
        retired.effect_stats[7] = 91
        corpse.effect_stats[7] = 22
        # OFF_PLAY remains visible, unlike the receipt-backed OUT actor.
        set_global_fighter_status(fight, corpse.id, "OFF_PLAY")
        corpse.hp = 0
        newborn = Actor(-9, 1, (1, 1, 0), 20, 3, 3, 1, 1)
        newborn.effect_stats = {7: 33}
        fight.actors[newborn.id] = newborn
        register_global_fighter(fight, newborn.id)
        serialize = lambda actor, _: struct.pack(">i", actor.effect_stats.get(7, 0))
        with patch.object(
            reconciliation, "_early_hidden_characteristics", return_value=None
        ):
            with patch.object(
                reconciliation, "_map_snapshot", wraps=reconciliation._map_snapshot
            ) as copy:
                original = reconciliation.changed_characteristic_packets(
                    fight, before, serialize
                )
                old_reads = [call.args[0] for call in copy.call_args_list]
        with patch.object(
            reconciliation, "_map_snapshot", wraps=reconciliation._map_snapshot
        ) as copy:
            actual = reconciliation.changed_characteristic_packets(
                fight, before, serialize
            )
            reads = [call.args[0] for call in copy.call_args_list]
        self.assertEqual(actual, original)
        self.assertEqual(
            actual,
            reconciliation.changed_characteristic_packets(
                fight, public_before, serialize
            ),
        )
        ids = [decode_actor_state(op, data)["actor_id"] for op, data in actual]
        self.assertEqual(ids, [corpse.id, newborn.id])
        hidden_maps = [getattr(retired, name) for name in reconciliation._MAPS]
        self.assertEqual(
            sum(any(value is row for row in hidden_maps) for value in old_reads), 8
        )
        self.assertFalse(any(value is row for value in reads for row in hidden_maps))
        self.assertEqual(retired.effect_stats[7], 91)  # No mutation or pruning.

        class CustomMap(dict):
            def items(self):
                observed.append(True)
                return super().items()

        observed = []
        retired.effect_stats = CustomMap(retired.effect_stats)
        self.assertIsNone(reconciliation._early_hidden_characteristics(fight))
        reconciliation.changed_characteristic_packets(fight, before, serialize)
        self.assertTrue(observed)
        retired.effect_stats = dict(retired.effect_stats)

        class UnreadHiddenValue:
            def __eq__(self, other):
                raise AssertionError("Hidden presentation values are not compared")

        retired.effect_stats[7] = UnreadHiddenValue()
        self.assertIn(retired.id, reconciliation._early_hidden_characteristics(fight))
        self.assertEqual(
            reconciliation.changed_characteristic_packets(fight, before, serialize),
            actual,
        )
        # Exercise the maintained actual RuntimeMessages expiration consumer.
        CharacteristicReconciliationTests().test_expiration_snapshot_only_still_reserves_action_boundary()
