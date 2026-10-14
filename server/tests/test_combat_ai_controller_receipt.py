"""Read-only receipt binds actual registered native controller state."""
import unittest
import test_combat_controller_registry as fixture
from wakfu_server.combat_ai_controller_receipt import controller_forecast_receipt
from wakfu_server.combat_controller_registry import transfer_native_controller


class AIControllerReceiptTests(unittest.TestCase):
    def test_actual_registry_and_published_book_binding(self):
        fight = fixture.NativeControllerRegistryTests().fight()
        target = fight.actors[-7]
        self.assertIsNone(controller_forecast_receipt(fight, target))
        transfer_native_controller(fight, -7, 7)
        fight.native_controller_action_books = {
            -7: dict(
                producer="eWD207.eZd.fQM.actual",
                running_uid=501,
                effect_reference=340345,
                caster_id=7,
                controller_id=7,
                applied_team=0,
                actions=(),
            )
        }
        receipt = controller_forecast_receipt(fight, target)
        self.assertEqual(
            (receipt["target_id"], receipt["current_team"], receipt["original_team"]),
            (-7, 0, 1),
        )
        self.assertEqual(fight.native_controller_action_books[-7]["running_uid"], 501)
        fight.native_controller_action_books[-7]["applied_team"] = 1
        with self.assertRaisesRegex(ValueError, "forecast controller authority"):
            controller_forecast_receipt(fight, target)

    def test_historical_book_grants_no_new_affiliation_authority(self):
        fight = fixture.NativeControllerRegistryTests().fight()
        target = fight.actors[-7]
        fight.native_controller_action_books = {
            -7: dict(
                producer="eWD207.eZd.fQM.actual",
                running_uid=501,
                controller_id=-7,
                actions=(),
            )
        }
        self.assertIsNone(controller_forecast_receipt(fight, target))

    def test_actual_retained_affiliation_payload_qualifies_only_current_team(self):
        from wakfu_server.combat_controller_registry import set_native_current_team
        from wakfu_server.combat_stat_effects import owned_effect_payload

        fight = fixture.NativeControllerRegistryTests().fight()
        actor = fight.actors[-7]
        set_native_current_team(fight, -7, 0)
        payload = owned_effect_payload(
            uid=601,
            base_uid=601,
            generic_effect=340426,
            caster_id=7,
            target_id=-7,
            value=0,
        )
        fight.owned_stat_effects = {
            601: dict(
                uid=601,
                family="eYV",
                effect_class=1030,
                target_id=-7,
                caster_id=7,
                actual=0,
                saved_affiliation=1,
                payload=payload.hex(),
            )
        }
        receipt = controller_forecast_receipt(fight, actor)
        self.assertEqual(
            (
                receipt["effect_class"],
                receipt["effect_reference"],
                receipt["current_team"],
            ),
            (1030, 340426, 0),
        )
        fight.owned_stat_effects[601]["actual"] = 1
        self.assertIsNone(controller_forecast_receipt(fight, actor))
