"""Father Doby offers his greeting independently of mission progress."""
import copy
import json
import sys
import types
import unittest
from collections import defaultdict
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from wakfu_server.achievements import mission_progress
from wakfu_server.maps import quest_npc


CONTRACT_PATH = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/native_quest_conversation_contracts.json"
)


class FakeDB:
    def __init__(self, row):
        self.row = row

    def execute(self, sql, params=()):
        self.sql = sql
        self.params = params
        return self

    def fetchone(self):
        if "world_dialogue_npcs" in self.sql:
            return self.row
        return {"id": 8}


class ContractDB:
    def __init__(self, document):
        self.document = document

    def execute(self, _sql, _params=()):
        return self

    def fetchone(self):
        return {"value": self.document}


class FakeStore:
    def __init__(self, db):
        self.db = db

    @contextmanager
    def connection(self):
        yield self.db

    def lock_character(self, *args, **kwargs):
        pass

    def character(self, account_id, character_id, db):
        return {
            "id": character_id,
            "account_id": account_id,
            "map_id": 507,
            "instance_id": 0,
            "x": 9,
            "y": -13,
            "z": 4,
        }

    def now(self):
        from datetime import datetime, timezone

        return datetime.fromtimestamp(42, timezone.utc)


class FakeDialogueSession:
    opened = []

    def __init__(self, *args, **kwargs):
        self.graph = args[1]

    def open(self, root, actor_id, authorize):
        self.opened.append((root, actor_id))
        return b"dialogue-open"


class DobyQuestNpcTests(unittest.TestCase):
    def setUp(self):
        self.document = json.loads(CONTRACT_PATH.read_text())
        self.doby = next(
            item for item in self.document["placements"] if item["quest_id"] == 1217
        )
        self.row = copy.deepcopy(self.doby["row"])
        self.definitions, self.bindings = __import__(
            "wakfu_server.achievements.conversation", fromlist=["validate_rules"]
        ).validate_rules(self.document)

    def invoke(self, running):
        db = FakeDB(self.row)
        store = FakeStore(db)
        state = {"running": running}
        FakeDialogueSession.opened = []
        with patch.object(
            quest_npc,
            "publication",
            return_value=(self.document, self.definitions, self.bindings),
        ), patch.object(quest_npc, "_owner"), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.npc_world": types.SimpleNamespace(
                    nearby=lambda *args: True
                )
            },
        ), patch.object(
            quest_npc.npc_dialogue, "catalog", return_value={"node_index": {}}
        ), patch.object(
            quest_npc.npc_dialogue, "DialogueSession", FakeDialogueSession
        ):
            result = quest_npc.begin(
                store,
                8,
                "lease",
                {"id": 7, "account_id": 8},
                self.row["actor_id"],
                304,
                character_provider=lambda: {"id": 7, "account_id": 8},
                rows_provider=lambda: [self.row],
            )
        return result

    def test_recurring_reset_in_compound_criterion_keeps_other_requirements(self):
        expression = "GetRealLevel() >= 105 and CanResetAchievement(1215)"
        self.assertTrue(
            quest_npc._criterion(
                None, {"level": 105}, expression, {}, reset_allowed=lambda i: i == 1215
            )
        )
        self.assertFalse(
            quest_npc._criterion(
                None, {"level": 104}, expression, {}, reset_allowed=lambda i: True
            )
        )
        self.assertFalse(
            quest_npc._criterion(
                None, {"level": 105}, expression, {}, reset_allowed=lambda i: False
            )
        )

    def test_published_doby_graph_qualifies_the_native_1217_objective(self):
        item = self.doby
        self.assertEqual(item["activation_policy"], "already_running")
        self.assertEqual(item["row"]["map_id"], 507)
        self.assertEqual(
            item["graph"],
            [
                [1986, 4658, 2046],
                [1986, 4555, 0],
                [1986, 4669, 2015],
                [2015, 4672, 2016],
                [2016, 4673, 0],
                [2046, 4713, 0],
                [1986, 4650, 2005],
                [2005, 4652, 0],
                [1986, 4651, 0],
            ],
        )
        edge = self.bindings[(2421, 304, 2046, 4713)]
        self.assertEqual((edge.quest_id, edge.objective_id), (1217, 2178))
        self.assertEqual(self.definitions[1217]["cjJ"][0]["d"], 2178)

    def test_doby_opens_with_or_without_the_mission(self):
        session, packets = self.invoke([1217])
        self.assertIn((1986, self.row["actor_id"]), FakeDialogueSession.opened)
        self.assertEqual(session.graph[(1986, 4658)], 2046)
        self.assertEqual(session.graph[(2046, 4713)], 0)
        self.assertEqual(packets, [b"dialogue-open"])

    def test_default_story_is_available_without_starting_a_quest(self):
        import gzip

        with gzip.open(
            Path(__file__).parents[1] / "protocol/npc-dialogues.json.gz", "rt"
        ) as source:
            native = json.load(source)
        nodes = {node["id"]: node for node in native["nodes"]}
        published = (self.document, self.definitions, self.bindings)
        scene_row = dict(self.row, _quest_publication=published)
        character = {
            "id": 7,
            "account_id": 8,
            "map_id": 507,
            "instance_id": 0,
            "x": 9,
            "y": -12,
            "z": 1,
        }
        store = FakeStore(FakeDB(self.row))
        store.character = lambda *args: dict(character)

        # This predicate represents the native criterion authority for a player
        # without an active mission; actual session/range and graph are used.
        criterion = (
            lambda _store, _character, expression, _queries, **kwargs: not expression
        )
        with patch.object(
            quest_npc, "publication", return_value=published
        ), patch.object(quest_npc, "_owner"), patch.object(
            quest_npc, "_criterion", side_effect=criterion
        ), patch.object(
            quest_npc, "queries", return_value={}
        ), patch.object(
            quest_npc.npc_dialogue, "catalog", return_value={"node_index": nodes}
        ), patch(
            "wakfu_server.achievements.storage.store"
        ) as store_progress, patch.dict(
            sys.modules,
            {
                "wakfu_server.npc_objective_facts": types.ModuleType(
                    "wakfu_server.npc_objective_facts"
                )
            },
        ):
            session, _packets = quest_npc.begin(
                store,
                8,
                "lease",
                character,
                self.row["actor_id"],
                304,
                character_provider=lambda: character,
                rows_provider=lambda: [scene_row],
            )
            with self.assertRaisesRegex(ValueError, "not offered"):
                session.choose(1986, 4658)
            session.choose(1986, 4669)
            self.assertEqual(session.node_id, 2015)
            session.choose(2015, 4672)
            self.assertEqual(session.node_id, 2016)
            session.choose(2016, 4673)
            self.assertIsNone(session.node_id)
            store_progress.assert_not_called()

        session, packets = self.invoke([])
        self.assertIn((1986, self.row["actor_id"]), FakeDialogueSession.opened)
        self.assertEqual(packets, [b"dialogue-open"])

    def test_doby_choice_advances_only_objective_2178_and_completes_mission(self):
        state = {
            "variables": {},
            "objectives": [],
            "running": [1217],
            "completed": [],
            "tracking": [1217],
            "recent": [],
            "completion_dates": {},
        }
        with patch("wakfu_server.dungeon_criteria.evaluate", return_value=True):
            (
                updated,
                rewards,
                objectives,
                completed,
            ) = mission_progress.advance_objective(
                state,
                self.definitions[1217],
                2178,
                character={"id": 7, "account_id": 8},
                store=object(),
                now_ms=42000,
            )
        self.assertEqual(objectives, [2178])
        self.assertEqual(completed, [1217])
        self.assertEqual(updated["objectives"], [2178])
        self.assertEqual(updated["running"], [])
        self.assertEqual(updated["completed"], [1217])
        self.assertEqual(updated["completion_dates"], {"1217": 42000})
        self.assertEqual([identity for identity, _reward in rewards], [1217])

    def test_reachable_approach_opens_dialogue_and_authorizes_progress(self):
        # Reproduce the player's observed approach; exercise the real range
        # check and dialogue session instead of stubbing nearby() to True.
        from wakfu_server.achievements import conversation

        character = {
            "id": 7,
            "account_id": 8,
            "map_id": 507,
            "instance_id": 0,
            "x": 9,
            "y": -12,
            "z": 1,
        }
        published = (self.document, self.definitions, self.bindings)
        scene_row = dict(self.row, _quest_publication=published)
        db = FakeDB(self.row)
        store = FakeStore(db)
        store.character = lambda *args: dict(character)
        state = {
            "variables": {},
            "objectives": [],
            "running": [1217],
            "completed": [],
            "tracking": [1217],
            "recent": [],
            "completion_dates": {},
        }
        nodes = {
            1986: {"criteria": "", "choices": [{"id": 4658, "criteria": ""}]},
            2046: {"criteria": "", "choices": [{"id": 4713, "criteria": ""}]},
        }
        with patch.object(
            quest_npc, "publication", return_value=published
        ), patch.object(quest_npc, "_owner"), patch.object(
            quest_npc, "_criterion", return_value=True
        ), patch.object(
            quest_npc, "queries", return_value={}
        ), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state
        ), patch.object(
            quest_npc.npc_dialogue, "catalog", return_value={"node_index": nodes}
        ), patch.dict(
            sys.modules,
            {
                "wakfu_server.npc_objective_facts": types.ModuleType(
                    "wakfu_server.npc_objective_facts"
                )
            },
        ):
            session, packets = quest_npc.begin(
                store,
                8,
                "lease",
                character,
                self.row["actor_id"],
                304,
                character_provider=lambda: character,
                rows_provider=lambda: [scene_row],
            )
            self.assertEqual(len(packets), 1)
            session.choose(1986, 4658)
            binding = self.bindings[(2421, 304, 2046, 4713)]
            fact = conversation.authorize_fact(
                character,
                self.row,
                session,
                binding,
                self.definitions[1217],
                node_id=2046,
                choice_id=4713,
            )
            with patch("wakfu_server.dungeon_criteria.evaluate", return_value=True):
                after, _, objectives, completed = conversation.advance(
                    state,
                    fact,
                    self.definitions[1217],
                    character=character,
                    store=store,
                    now_ms=42000,
                )
            self.assertEqual((objectives, completed), ([2178], [1217]))
            self.assertIn(1217, after["completed"])
            session.choose(2046, 4713)

    def test_native_position_and_separate_interaction_anchor(self):
        self.assertEqual((self.row["x"], self.row["y"], self.row["z"]), (9, -13, 4))
        character = {"map_id": 507, "instance_id": 0, "x": 9, "y": -12, "z": 1}
        with patch.dict(
            sys.modules,
            {
                "wakfu_server.npc_objective_facts": types.ModuleType(
                    "wakfu_server.npc_objective_facts"
                )
            },
        ):
            self.assertTrue(quest_npc._nearby_placement(character, self.row, self.doby))
            self.assertFalse(
                quest_npc._nearby_placement(dict(character, z=6), self.row, self.doby)
            )
            self.assertFalse(
                quest_npc._nearby_placement(dict(character, x=100), self.row, self.doby)
            )
            self.assertFalse(
                quest_npc._nearby_placement(
                    dict(character, map_id=508), self.row, self.doby
                )
            )

    def test_completing_doby_mission_unlocks_and_tracks_mission_1220(self):
        speakers = {}
        choices = defaultdict(set)
        for placement in self.document["placements"]:
            row = placement["row"]
            speakers[row["reference_id"]] = {
                "ref": row["reference_id"],
                "actions": [{"id": action_id} for action_id in row["action_ids"]],
            }
            for node_id, choice_id, _target in placement["graph"]:
                choices[node_id].add(choice_id)
        native_catalog = {
            "speakers": list(speakers.values()),
            "node_index": {
                node_id: {"choices": [{"id": choice} for choice in node_choices]}
                for node_id, node_choices in choices.items()
            },
        }
        with patch.object(
            quest_npc.npc_dialogue, "catalog", return_value=native_catalog
        ):
            published = quest_npc.publication(ContractDB(self.document))
        self.assertIn(1217, published[1])
        self.assertEqual(published[1][1220]["cjI"], "GetRealLevel() >= 105")

        link = next(
            value
            for value in self.document["activation_links"]
            if value.get("after_quest") == 1217
        )
        self.assertEqual(link["start_quest"], 1220)
        self.assertEqual(link["policy"], "reconstructed_narrative")
        self.assertTrue(link["evidence"].strip())
        self.assertEqual(self.definitions[1220]["cjI"], "GetRealLevel() >= 105")
        state = {
            "variables": {},
            "objectives": [2178],
            "running": [],
            "completed": [1217],
            "tracking": [],
            "recent": [],
            "completion_dates": {"1217": 42000},
        }
        db = FakeDB(self.row)
        with patch(
            "wakfu_server.achievements.storage.load_locked", return_value=state
        ), patch.object(quest_npc, "_criterion", return_value=True), patch(
            "wakfu_server.achievements.storage.record_event", return_value=True
        ) as record, patch(
            "wakfu_server.achievements.storage.store"
        ) as persist, patch(
            "wakfu_server.achievements.wire.changes", return_value=[b"mission-1220"]
        ):
            packets = quest_npc._activate(
                db,
                FakeStore(db),
                {"id": 7, "account_id": 8},
                self.row,
                self.definitions[1220],
            )
        self.assertEqual(packets, [b"mission-1220"])
        self.assertEqual(
            record.call_args.args[2], "native-quest-conversation-activation:1220"
        )
        updated = persist.call_args.args[2]
        self.assertEqual(updated["running"], [1220])
        self.assertEqual(updated["tracking"], [1220])


if __name__ == "__main__":
    unittest.main()
