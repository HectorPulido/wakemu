"""Native mercenary prerequisites use owned effective level and rank history."""

from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import unittest
from unittest.mock import patch

from wakfu_server.achievements import (
    combat_mission_activation,
    mission_toolkit_planner,
    native_effective_eligibility,
)
from wakfu_server.maps import dungeon_criteria, quest_npc


ROOT = Path(__file__).resolve().parents[1]
INDEX = json.loads(
    (ROOT / "wakfu_server/achievements/native_mercenary_ranks.json").read_text()
)
RANKS = {row["d"]: row for row in INDEX["definitions"]}
NATIVE = json.loads(
    (
        ROOT.parent / ".runtime/quest-extraction/native-quest-definitions.json"
    ).read_text()
)
NATIVE_BY_ID = {row["d"]: row for row in NATIVE["definitions"]}
LOWER = {
    2138: (2143, 2144, 2145, 2146),
    2139: (2147, 2149, 2150, 2151),
}


def definition(identity):
    row = deepcopy(NATIVE_BY_ID[identity])
    # Keep the exact rank identity pinned by the reviewed 95-contract index.
    for key, value in RANKS[identity].items():
        row[key] = value
    return row


def state(completed=()):
    return {
        "running": [],
        "completed": list(completed),
        "objectives": [],
        "tracking": [],
        "variables": {},
        "completion_dates": {},
        "recent": [],
    }


class NativeEffectiveEligibilityTests(unittest.TestCase):
    def test_rank_criteria_require_every_lower_same_category_contract(self):
        for identity, required in LOWER.items():
            with self.subTest(quest=identity):
                effective = native_effective_eligibility.criterion(definition(identity))
                self.assertTrue(effective.startswith("(GetLevel() >= 6 && "))
                extracted = tuple(
                    int(value)
                    for value in re.findall(
                        r"IsAchievementComplete\((\d+)\)", effective
                    )
                )
                self.assertEqual(extracted, required)
                self.assertNotIn("IsAchievementActive", effective)

    def test_rank_index_fails_closed_and_preserves_native_cji(self):
        candidate = definition(2138)
        candidate["cjP"] += 1
        with self.assertRaisesRegex(ValueError, "Unqualified native mercenary"):
            native_effective_eligibility.criterion(candidate)
        for mutated in (
            {"cjW": False},
            {"cjW": None},
            {"cjW": "true"},
            {"cjW": "missing"},
        ):
            with self.subTest(mutated=mutated), self.assertRaises(ValueError):
                native_effective_eligibility.criterion({**definition(2138), **mutated})
        unknown = definition(2138)
        unknown["d"] = 999999
        with self.assertRaisesRegex(ValueError, "Unqualified native mercenary"):
            native_effective_eligibility.criterion(unknown)

        non_mercenary = {"d": 1, "cjW": False, "cjI": "GetRealLevel() >= 5"}
        self.assertEqual(
            native_effective_eligibility.criterion(non_mercenary),
            "GetRealLevel() >= 5",
        )

    def test_optional_license_guard_is_compiled_without_rewriting_cji(self):
        row = {
            "d": 90001,
            "cjG": 99,
            "cjY": 2,
            "cjP": 6,
            "cjX": 451,
            "cjI": "IsAchievementComplete(12)",
        }
        with patch.object(
            native_effective_eligibility, "_index", return_value={90001: row}
        ):
            result = native_effective_eligibility.criterion({**row, "cjW": True})
        self.assertIn("GetItemQuantity(451) > 0", result)
        self.assertTrue(result.endswith("&& (IsAchievementComplete(12))"))
        self.assertEqual(sum(item["cjX"] > 0 for item in INDEX["definitions"]), 0)

    def test_getlevel_uses_explicit_effective_level_only(self):
        expression = "GetLevel() >= 6 && GetRealLevel() >= 1"
        self.assertTrue(
            dungeon_criteria.evaluate(
                None,
                expression,
                character={"effective_level": 6, "level": 1},
                queries={},
                now_ms=0,
            )
        )
        self.assertFalse(
            dungeon_criteria.evaluate(
                None,
                expression,
                character={"effective_level": 5, "level": 99},
                queries={},
                now_ms=0,
            )
        )
        for character in ({"level": 99}, {"effective_level": True, "level": 99}):
            with self.subTest(character=character), self.assertRaisesRegex(
                ValueError, "effective character level"
            ):
                dungeon_criteria.evaluate(
                    None,
                    "GetLevel() >= 6",
                    character=character,
                    queries={},
                    now_ms=0,
                )
        with self.assertRaises(ValueError):
            dungeon_criteria.evaluate(
                None,
                "GetLevel(foo=1) >= 6",
                character={"effective_level": 6},
                queries={},
                now_ms=0,
            )

    def test_combat_autoaccept_waits_for_exact_lower_ranks_and_effective_level(self):
        for identity, required in LOWER.items():
            with self.subTest(quest=identity):
                native = definition(identity)
                native["aHe"] = "False"  # Visibility must not become eligibility.
                rule = [{"kind": "monster", "target_id": 1710, "quest_id": identity}]
                event = {"original_breeds": [1710]}
                character = {"id": 1, "level": 6, "effective_level": 5}
                plan, started = combat_mission_activation.auto_accept(
                    state(required),
                    event,
                    rule,
                    {identity: native},
                    character=character,
                    store=None,
                    now_ms=1,
                )
                self.assertEqual(started, [])
                self.assertNotIn(identity, plan["running"])

                character["effective_level"] = 6
                plan, started = combat_mission_activation.auto_accept(
                    state(required[:-1]),
                    event,
                    rule,
                    {identity: native},
                    character=character,
                    store=None,
                    now_ms=1,
                )
                self.assertEqual(started, [])
                self.assertNotIn(identity, plan["running"])

                plan, started = combat_mission_activation.auto_accept(
                    state(required),
                    event,
                    rule,
                    {identity: native},
                    character=character,
                    store=None,
                    now_ms=1,
                )
                self.assertEqual(started, [identity])
                self.assertIn(identity, plan["running"])

    def test_toolkit_and_npc_admission_share_native_rank_gate(self):
        identity = 2138
        native = definition(identity)
        required = LOWER[identity]
        character = {"id": 3, "map_id": 527, "level": 6, "effective_level": 6}
        declaration = [
            {
                "id": "test-rank-followup",
                "quest_id": identity,
                "event": {"kind": "quest_completed", "reference": 9000},
                "requires_completed": [9000],
            }
        ]
        event = {"kind": "quest_completed", "reference": 9000}
        candidate = state((*required[:-1], 9000))
        self.assertFalse(
            mission_toolkit_planner._activate(
                candidate,
                {identity: native},
                declaration,
                [event],
                character=character,
                store=None,
                now_ms=1,
            )
        )
        candidate = state((*required, 9000))
        self.assertTrue(
            mission_toolkit_planner._activate(
                candidate,
                {identity: native},
                declaration,
                [event],
                character=character,
                store=None,
                now_ms=1,
            )
        )
        self.assertIn(identity, candidate["running"])

        npc_state = state(required[:-1])
        persisted = {}
        fake_store = type(
            "Clock", (), {"now": lambda self: datetime.now(timezone.utc)}
        )()
        with (
            patch.object(
                quest_npc.storage, "load_locked", return_value=deepcopy(npc_state)
            ),
            patch.object(
                quest_npc.storage, "record_event", return_value=True
            ) as record,
            patch.object(
                quest_npc.storage,
                "store",
                side_effect=lambda db, owner, value: persisted.update(value),
            ),
            patch.object(quest_npc.wire, "changes", return_value=[("wire", b"ok")]),
        ):
            self.assertEqual(
                quest_npc._activate(
                    object(),
                    fake_store,
                    character,
                    {"actor_id": 77},
                    native,
                    defer_unavailable=True,
                ),
                [],
            )
            record.assert_not_called()
            self.assertEqual(persisted, {})

        npc_state = state(required)
        persisted.clear()
        with (
            patch.object(
                quest_npc.storage, "load_locked", return_value=deepcopy(npc_state)
            ),
            patch.object(quest_npc.storage, "record_event", return_value=True),
            patch.object(
                quest_npc.storage,
                "store",
                side_effect=lambda db, owner, value: persisted.update(value),
            ),
            patch.object(quest_npc.wire, "changes", return_value=[("wire", b"ok")]),
        ):
            self.assertEqual(
                quest_npc._activate(
                    object(), fake_store, character, {"actor_id": 77}, native
                ),
                [("wire", b"ok")],
            )
        self.assertIn(identity, persisted["running"])


if __name__ == "__main__":
    unittest.main()
