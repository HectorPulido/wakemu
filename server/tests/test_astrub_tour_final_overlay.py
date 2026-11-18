"""The final Astrub tour branch overlays the unchanged captured Goultard."""
from contextlib import contextmanager
from copy import deepcopy
import json
from pathlib import Path
import unittest
from unittest.mock import patch

from wakfu_server import native_catalog, quest_npc
from wakfu_server.achievements import conversation
from wakfu_server import npc_dialogue_source_overlay


ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = ROOT.parent / ".runtime/quest-archetypes/line4/npc-candidate.json"
ACTOR_ID = -1776810790485981
ACTION_ID = 969


class CandidateDB:
    def __init__(self, value):
        self.value = value

    def execute(self, *_args):
        return self

    def fetchone(self):
        return {"value": self.value}


class OverlayStore:
    def __init__(self, state):
        self.state = state

    @contextmanager
    def connection(self):
        yield self

    def execute(self, *_args):
        return self

    def fetchone(self):
        return {"id": 7}

    def lock_character(self, *_args, **_kwargs):
        pass

    def character(self, account_id, character_id, _db):
        return {
            "id": character_id,
            "account_id": account_id,
            "map_id": 527,
            "instance_id": 0,
            "x": 11,
            "y": 155,
            "z": 0,
        }


class AstrubTourFinalOverlayTests(unittest.TestCase):
    def test_candidate_projects_virtual_goultard_only_for_earned_running_branch(self):
        candidate = json.loads(CANDIDATE.read_text())
        item = next(
            row for row in candidate["placements"] if row["row"]["actor_id"] == ACTOR_ID
        )
        self.assertEqual(item["row"]["dialogue_root"], 4149)
        self.assertEqual(item["row"]["native_capture_id"], ACTOR_ID)
        self.assertEqual(item["row"]["action_ids"], [ACTION_ID])
        self.assertEqual(
            item["existing_dialogue_actor"]["source_sha256"],
            "bf84a92d0c33851c8ecc74367dfb6035844a65979be9c6bfd069db8b4f5de325",
        )

        with patch.object(
            quest_npc,
            "source_contract_digest",
            return_value=conversation._digest(candidate),
        ):
            published = quest_npc.publication(CandidateDB(candidate))
        self.assertEqual(len(published[0]["placements"]), 46)

        changed_root = deepcopy(candidate)
        next(
            row
            for row in changed_root["placements"]
            if row["row"]["actor_id"] == ACTOR_ID
        )["row"]["dialogue_root"] = 7119
        with patch.object(
            quest_npc,
            "source_contract_digest",
            return_value=conversation._digest(changed_root),
        ):
            with self.assertRaisesRegex(ValueError, "disconnected edge"):
                quest_npc.publication(CandidateDB(changed_root))

        with native_catalog._database().connection() as real_db:
            source = npc_dialogue_source_overlay.validate(real_db, item)
            self.assertEqual(source["actor_id"], ACTOR_ID)
            self.assertEqual(source["dialogue_root"], 7119)
            self.assertEqual(source["action_ids"], [ACTION_ID])

            projected, selected = quest_npc._row(real_db, ACTOR_ID, published)
            self.assertIs(selected, item)
            self.assertEqual(projected["dialogue_root"], 4149)
            self.assertEqual(projected["actor_id"], ACTOR_ID)
            self.assertEqual(projected["native_capture_id"], ACTOR_ID)
            self.assertEqual(projected["_quest_publication"], published)
            current = real_db.execute(
                "SELECT dialogue_root FROM world_dialogue_npcs WHERE actor_id=%s",
                (ACTOR_ID,),
            ).fetchone()
            self.assertEqual(current["dialogue_root"], 7119)

            for label, mutate in (
                (
                    "source pin",
                    lambda bad: bad["existing_dialogue_actor"].update(
                        source_sha256="0" * 64
                    ),
                ),
                ("physical pose", lambda bad: bad["row"].update(x=12)),
                (
                    "interaction range",
                    lambda bad: bad["row"].update(interaction_range=5),
                ),
                ("action", lambda bad: bad["row"].update(action_ids=[970])),
            ):
                bad = deepcopy(item)
                mutate(bad)
                with self.subTest(label=label), self.assertRaises(ValueError):
                    npc_dialogue_source_overlay.validate(real_db, bad)

        character = {
            "id": 41,
            "account_id": 7,
            "map_id": 527,
            "instance_id": 0,
            "x": 11,
            "y": 155,
            "z": 0,
        }
        inactive = {
            "running": [],
            "active": [],
            "active_periods": {},
            "completed": [],
            "objectives": [],
            "variables": {},
            "completion_dates": {},
        }
        earned = {
            "running": [5569],
            "active": [5569],
            "active_periods": {},
            "completed": [],
            "objectives": [11516, 11517, 11518],
            "variables": {},
            "completion_dates": {},
        }
        result = object()

        def validate_source(_db, overlay):
            with native_catalog._database().connection() as real_db:
                return npc_dialogue_source_overlay.validate(real_db, overlay)

        with (
            patch.object(quest_npc, "publication", return_value=published),
            patch.object(quest_npc, "_existing_actor", side_effect=validate_source),
            patch.object(quest_npc, "_owner"),
            patch(
                "wakfu_server.achievements.storage.load_locked",
                side_effect=lambda _db, _id: self._state,
            ),
            patch.object(quest_npc, "begin", return_value=result) as begin,
            patch.object(quest_npc, "_activate") as activate,
        ):
            self._state = inactive
            self.assertIsNone(
                quest_npc.try_native_overlay(
                    OverlayStore(inactive),
                    7,
                    "lease",
                    character,
                    ACTOR_ID,
                    ACTION_ID,
                    character_provider=lambda: character,
                    provider_field="existing_dialogue_actor",
                )
            )
            begin.assert_not_called()
            self._state = earned
            active_result = quest_npc.try_native_overlay(
                OverlayStore(earned),
                7,
                "lease",
                character,
                ACTOR_ID,
                ACTION_ID,
                character_provider=lambda: character,
                provider_field="existing_dialogue_actor",
            )
            self.assertIs(active_result, result)
            begin.assert_called_once()
            self.assertEqual(begin.call_args.args[4:6], (ACTOR_ID, ACTION_ID))
            self.assertEqual(
                begin.call_args.kwargs["rows_provider"]()[0]["dialogue_root"], 4149
            )
            activate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
