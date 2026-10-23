"""Admission freezes the original Ombrage timer listener from database policy."""
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import patch

from postgres_case import PostgresCase


class OmbrageTableListenerCatalogTests(PostgresCase):
    def test_database_freeze_pins_original_damage_deadline_and_rejects_drift(self):
        from wakfu_server import combat_encounter_table_listeners as listeners

        listeners._version.cache_clear()
        self.addCleanup(listeners._version.cache_clear)
        with patch.object(listeners, "_database", return_value=self.store):
            frozen = listeners.freeze_table_listener_policy(1229, (4770,))
            self.assertEqual(
                frozen["policy"], "wakemu-ombrage-damage-deadline-table-listener-v1"
            )
            self.assertEqual(
                (
                    frozen["boss_reference"],
                    frozen["boss_constructor_state"],
                    frozen["owner_reference"],
                    frozen["owner_constructor_state"],
                    frozen["effect_reference"],
                    frozen["event_id"],
                    frozen["channel"],
                ),
                (4770, 5649, 4770, 5659, 266725, 1003, 61),
            )
            fight = SimpleNamespace(
                native_encounter_table_listener_policy=deepcopy(frozen)
            )
            self.assertEqual(listeners.frozen_table_listener_policy(fight), frozen)
            with self.store.connection() as db:
                db.execute(
                    "DELETE FROM encounter_table_listener_active WHERE map_id=1229"
                )
            self.assertIsNone(
                listeners.freeze_table_listener_policy(1229, (4770,), required=False)
            )
            self.assertEqual(listeners.frozen_table_listener_policy(fight), frozen)
            fight.native_encounter_table_listener_policy["effect_reference"] = 266402
            with self.assertRaisesRegex(ValueError, "policy changed"):
                listeners.frozen_table_listener_policy(fight)
