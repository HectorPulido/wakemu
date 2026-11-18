"""Optional rescue uses native quest variants and normal token settlement."""

from copy import deepcopy
from datetime import datetime, timezone
from hashlib import sha256
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from wakfu_server import owned_companion_rescue as module
from wakfu_server.achievements import owned_quest_encounters

DEFINITIONS = json.loads(
    (
        Path(__file__).with_name("fixtures") / "astrub_knight_native_quests.json"
    ).read_text()
)
PIN = dict(
    path="astrub-knight.json",
    sha256=sha256((module.ROOT / "astrub-knight.json").read_bytes()).hexdigest(),
)


class OwnedCompanionRescueTests(unittest.TestCase):
    def setUp(self):
        self.selected = dict(map_id=887, optional_companion=PIN)
        self.character = dict(
            id=7, account_id=3, map_id=887, instance_id=99, x=5, y=-58, z=12
        )
        self.store = SimpleNamespace(
            now=lambda: datetime(2026, 11, 15, tzinfo=timezone.utc)
        )
        self.state = dict(
            running=[1726],
            completed=[2166, 2170],
            objectives=[],
            variables={},
            counters={},
            tracked=[],
        )
        self.native = json.loads(
            (
                Path(__file__).parents[1]
                / "wakfu_server/maps/owned_story_profiles/astrub-temple-887.native.v1.json"
            ).read_text()
        )
        self.db = Mock()
        self.db.execute.return_value.fetchone.return_value = dict(
            data=dict(native=DEFINITIONS["1726"])
        )
        self.stack = __import__("contextlib").ExitStack()
        self.addCleanup(self.stack.close)
        for target, name, value in (
            (module.controller, "_scope", (self.selected, set())),
            (module.mechanics, "sources", self.native),
            (module.mechanics, "allowed", True),
            (module.storage, "load_locked", self.state),
        ):
            self.stack.enter_context(patch.object(target, name, return_value=value))

    def test_cage_requires_victory_and_selects_only_actual_running_native_variant(self):
        with patch.object(
            owned_quest_encounters, "_advance", return_value=[(13422, b"progress")]
        ) as advance:
            self.state["completed"].remove(2170)
            self.assertEqual(
                module.interact(
                    self.db, self.store, self.character, self.selected, 23583, 0
                ),
                [],
            )
            advance.assert_not_called()
            self.state["completed"].append(2170)
            self.assertEqual(
                module.interact(
                    self.db, self.store, self.character, self.selected, 23583, 0
                ),
                [(13422, b"progress")],
            )
            self.assertEqual(
                advance.call_args.args[4:6], (3299, "owned-companion-rescue:1726")
            )
            self.state["completed"].append(1726)
            advance.reset_mock()
            self.assertEqual(
                module.interact(
                    self.db, self.store, self.character, self.selected, 23583, 0
                ),
                [],
            )
            advance.assert_not_called()

    def test_legacy_variant_is_preserved_and_duplicate_family_is_not_rewarded(self):
        self.state["running"] = [1721]
        self.db.execute.return_value.fetchone.return_value = dict(
            data=dict(native=DEFINITIONS["1721"])
        )
        with patch.object(
            owned_quest_encounters, "_advance", return_value=[]
        ) as advance:
            module.interact(
                self.db, self.store, self.character, self.selected, 23583, 0
            )
            self.assertEqual(advance.call_args.args[4], 3292)
            advance.reset_mock()
            self.state["running"].append(1726)
            module.interact(
                self.db, self.store, self.character, self.selected, 23583, 0
            )
            advance.assert_not_called()

    def test_scope_distance_disabled_configuration_and_changed_native_definition_reject(
        self,
    ):
        with patch.object(owned_quest_encounters, "_advance") as advance:
            self.character["x"] = 20
            with self.assertRaisesRegex(ValueError, "range"):
                module.interact(
                    self.db, self.store, self.character, self.selected, 23583, 0
                )
            self.character["x"] = 5
            with patch.object(
                module.controller, "_scope", return_value=(dict(map_id=527), set())
            ):
                with self.assertRaisesRegex(ValueError, "scope"):
                    module.interact(
                        self.db, self.store, self.character, self.selected, 23583, 0
                    )
            with patch.object(module.mechanics, "allowed", return_value=False):
                self.assertEqual(
                    module.interact(
                        self.db, self.store, self.character, self.selected, 23583, 0
                    ),
                    [],
                )
            broken = deepcopy(DEFINITIONS["1726"])
            broken["cjK"] = []
            self.db.execute.return_value.fetchone.return_value = dict(
                data=dict(native=broken)
            )
            with self.assertRaisesRegex(ValueError, "definition changed"):
                module.interact(
                    self.db, self.store, self.character, self.selected, 23583, 0
                )
            advance.assert_not_called()

    def test_admission_is_explicit_temple_entry_not_display_level_or_ownership(self):
        self.state["running"] = [2170]
        self.state["completed"] = [2166]
        with patch.object(
            module.mission_dependencies,
            "settle",
            return_value=dict(packets=[(13422, b"activation")]),
        ) as settle, patch.object(
            module.mission_progress, "seed_counters"
        ), patch.object(
            module.mission_progress, "auto_track"
        ), patch.object(
            module.storage, "record_event", return_value=True
        ):
            self.assertEqual(
                module.admit(self.db, self.store, self.character, self.selected),
                [(13422, b"activation")],
            )
            planned = settle.call_args.args[4]
            self.assertEqual(planned[0]["running"], [1726, 2170])
            self.assertEqual(planned[1:], ([], [], []))
            self.assertNotIn(1726, self.state["running"])
            self.state["completed"] = []
            settle.reset_mock()
            self.assertEqual(
                module.admit(self.db, self.store, self.character, self.selected), []
            )
            settle.assert_not_called()

    def test_malformed_or_changed_policy_pin_fails_with_value_error(self):
        for pin in (
            True,
            [],
            {},
            {"path": "astrub-knight.json", "sha256": 7},
            {"path": "../escape.json", "sha256": "0" * 64},
            dict(PIN, extra=True),
        ):
            with self.subTest(pin=pin), self.assertRaises(ValueError):
                module.policy(dict(map_id=887, optional_companion=pin))

    def test_compatibility_attaches_only_exact_published_controller_without_repin(self):
        source = (
            Path(__file__).parents[1]
            / "wakfu_server/maps/owned_story_profiles/astrub-temple-887.configuration.json"
        )
        selected = json.loads(source.read_text())["topology"]["owned_story_controller"]
        frozen = deepcopy(selected)
        self.assertNotIn("optional_companion", selected)
        self.assertEqual(module.policy(selected)["preferred_quest_id"], 1726)
        self.assertEqual(selected, frozen)
        self.assertTrue(module.can_reenter(selected, dict(completed=[2166, 2170])))
        self.assertFalse(module.can_reenter(selected, dict(completed=[2166])))
        for variant in (1721, 1726):
            self.assertFalse(
                module.can_reenter(selected, dict(completed=[2166, 2170, variant]))
            )
        changed = deepcopy(selected)
        changed["id"] += "-unreviewed"
        self.assertIsNone(module.policy(changed))
        self.assertFalse(module.can_reenter(changed, dict(completed=[2166, 2170])))
