import unittest
from unittest.mock import Mock, patch
from wakfu_server.item_mutation import refresh_equipment_after_mutation
from wakfu_server.wire import proto_field


class ItemMutationTests(unittest.TestCase):
    def character(self, *, active=0):
        equipment = proto_field(10, proto_field(8, 17)).hex()
        return dict(
            id=3,
            account_id=2,
            active_build_index=active,
            builds={0: dict(equipment=equipment)},
            max_hp=100,
            hp_damage=30,
            health_dead=False,
        )

    def test_active_equipment_recomputes_maximum_without_healing(self):
        character = self.character()
        store, db = Mock(), Mock()
        store.character.return_value = character
        store.now.return_value = 50
        with patch(
            "wakfu_server.equipment_stats.effective_character",
            return_value={"max_hp": 120},
        ):
            with refresh_equipment_after_mutation(store, db, 2, 3, 17):
                pass
        self.assertEqual(db.execute.call_args_list[0].args[1], (90, 120, 3, 2))
        self.assertEqual(db.execute.call_args_list[1].args[1], (90, 50, 50, 3))

    def test_inactive_reference_does_not_change_health(self):
        store, db = Mock(), Mock()
        store.character.return_value = self.character(active=1)
        with refresh_equipment_after_mutation(store, db, 2, 3, 17):
            pass
        db.execute.assert_not_called()

    def test_failed_mutation_does_not_publish_reconfigured_health(self):
        store, db = Mock(), Mock()
        store.character.return_value = self.character()
        with self.assertRaisesRegex(ValueError, "rollback"):
            with refresh_equipment_after_mutation(store, db, 2, 3, 17):
                raise ValueError("rollback")
        db.execute.assert_not_called()
