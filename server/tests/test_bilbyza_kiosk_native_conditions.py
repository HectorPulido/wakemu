"""Bilbyza kiosk native conditions remain authoritative on every path."""
from copy import deepcopy
import json
from pathlib import Path
import unittest

from test_interactive_missions import InteractiveMissionAdapterTests
from tools import publish_native_generic_rewards as publisher
from wakfu_server.maps import native_generic_rewards


KIOSK_CRITERION = (
    "GetRealLevel()>=85 && GetItemQuantity(17515) == 0 "
    "&& not IsAchievementComplete(1260)"
)
REPLACEMENT_LOOT_CRITERION = (
    "IsAchievementComplete(1260) && GetItemQuantity(17515) == 0"
)
ROOT = Path(__file__).parents[1]
CLUE_PROFILE = (
    ROOT / "wakfu_server/maps/native_generic_profiles/wild-estate-clue-feedback.json"
)


def _kiosk_entry(*, effect_reference=2537, criterion=KIOSK_CRITERION, external=True):
    """Use an absent-client-script source shape with pinned local source hashes."""
    entry = json.loads(CLUE_PROFILE.read_text())["entries"][0]
    entry = deepcopy(entry)
    program = entry["program"]
    program["descriptor_id"] = 162
    source = entry["source"]
    source.update(descriptor_id=162, map_id=143, id=18974)
    entry["state"] = None
    action = program["groups"][0]["actions"][0]
    action["effects"][0].update(
        action_reference=effect_reference,
        criterion=criterion,
        parameters=["false"],
    )
    entry["approaches"] = [[16, 12, -80]]
    entry["script_sources"] = {}
    if external:
        entry["external_quest_scripts"] = [
            dict(
                effect_reference=effect_reference,
                quest_id=1260,
                objective_id=2389,
                native_criterion=criterion,
            )
        ]
    else:
        entry.pop("external_quest_scripts", None)
    return entry


class BilbyzaInteractiveMissionGuardTests(unittest.TestCase):
    def test_guarded_milestone_denial_has_no_receipt_progress_payment_or_reward(self):
        fixture = InteractiveMissionAdapterTests()
        fixture.setUp()
        fixture.row["native_criterion"] = KIOSK_CRITERION
        fixture.row["native_effect_reference"] = 162
        (
            result,
            _store,
            receipt,
            persist,
            claim,
            _changes,
            drain,
            payment,
        ) = fixture.invoke(criterion_result=False)

        self.assertFalse(result["applied"])
        self.assertFalse(result["handled"])
        self.assertEqual(result["packets"], [])
        fixture.last_criterion_evaluate.assert_called_once()
        self.assertEqual(
            fixture.last_criterion_evaluate.call_args.args[1], KIOSK_CRITERION
        )
        receipt.assert_not_called()
        persist.assert_not_called()
        claim.assert_not_called()
        drain.assert_not_called()
        payment.assert_not_called()
        fixture.last_settlement.assert_not_called()

    def test_legacy_binding_without_native_condition_keeps_existing_behavior(self):
        fixture = InteractiveMissionAdapterTests()
        fixture.setUp()
        self.assertEqual(fixture.row.get("native_criterion", ""), "")
        self.assertEqual(fixture.row.get("native_effect_reference", 0), 0)
        (
            result,
            _store,
            _receipt,
            _persist,
            _claim,
            _changes,
            _drain,
            _payment,
        ) = fixture.invoke()
        self.assertTrue(result["applied"])
        self.assertTrue(fixture.last_criterion_evaluate.called)
        self.assertNotIn(
            KIOSK_CRITERION,
            [call.args[1] for call in fixture.last_criterion_evaluate.call_args_list],
        )


class BilbyzaGenericPublisherGuardTests(unittest.TestCase):
    def test_exact_absent_script_with_matching_external_declaration_compiles(self):
        rule, effects, location, _tables = publisher._records(_kiosk_entry())
        self.assertEqual(location["map_id"], 143)
        self.assertEqual(location["object_id"], 18974)
        self.assertEqual(rule["wire_action"], 0)
        self.assertEqual(
            [
                (effect["effect_reference"], effect["effect_type"], effect["criterion"])
                for effect in effects
            ],
            [(2537, 1, KIOSK_CRITERION)],
        )

    def test_external_callback_rejects_unknown_effect_missing_lua_and_lua_mislabeled(
        self,
    ):
        unknown = _kiosk_entry()
        unknown["external_quest_scripts"][0]["effect_reference"] = 99999
        with self.assertRaises(ValueError):
            publisher._records(unknown)

        missing_without_binding = _kiosk_entry(external=False)
        with self.assertRaisesRegex(ValueError, "script source is absent"):
            publisher._records(missing_without_binding)

        existing_lua_as_server_only = _kiosk_entry(effect_reference=2316)
        with self.assertRaisesRegex(ValueError, "must retain its absent"):
            publisher._records(existing_lua_as_server_only)

    def test_install_rejects_external_script_without_matching_installed_binding(self):
        class NoBindingDB:
            def __init__(self):
                self.queries = []

            def execute(self, sql, params=()):
                self.queries.append((sql, params))
                return self

            def fetchone(self):
                return None

        with self.assertRaisesRegex(ValueError, "exact installed guarded interaction"):
            publisher.install(
                NoBindingDB(),
                {"schema": publisher.SCHEMA, "entries": [_kiosk_entry()]},
            )

    def test_original_positive_conjunction_is_accepted_and_or_bypass_rejected(self):
        bypass = REPLACEMENT_LOOT_CRITERION.replace("&&", "||", 1)
        self.assertEqual(
            (
                native_generic_rewards._positive_inventory_guard(
                    REPLACEMENT_LOOT_CRITERION, 17515
                ),
                native_generic_rewards._positive_inventory_guard(bypass, 17515),
                native_generic_rewards._positive_inventory_guard(
                    KIOSK_CRITERION, 17515
                ),
            ),
            (True, False, False),
        )


if __name__ == "__main__":
    unittest.main()
