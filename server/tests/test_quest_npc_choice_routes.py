"""Only an accepted native dialogue choice may enter a declared route."""

import gzip
import json
import struct
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

from wakfu_server import quest_npc
from wakfu_server.achievements import conversation


ROOT = Path(__file__).resolve().parents[2]


class _DB:
    def execute(self, *_args, **_kwargs):
        return self


class _Store:
    @contextmanager
    def connection(self):
        yield _DB()

    def lock_character(self, *_args, **_kwargs):
        pass

    def character(self, account_id, character_id, _db):
        return {
            "id": character_id,
            "account_id": account_id,
            "map_id": 527,
            "instance_id": 0,
            "x": 108,
            "y": -20,
            "z": 0,
        }


class _Session:
    def __init__(self, node, actor):
        self.nodes = {node["id"]: node}
        self.graph = {(node["id"], 7954): None}
        self.node_id = node["id"]
        self.speaker_id = actor
        self.previous_choice_id = None
        self.quest_conversation_actor_id = actor
        self.authorize_speaker = lambda speaker, root: (speaker, root) == (
            actor,
            node["id"],
        )
        self.authorize_node = lambda _node: True
        self.authorize_choice = lambda choice: choice["id"] == 7954

    def _node(self, node_id):
        return self.nodes[node_id]

    def choose(self, *, node_id, choice_id):
        node = self.nodes[node_id]
        choice = next((row for row in node["choices"] if row["id"] == choice_id), None)
        if (
            self.node_id != node_id
            or choice is None
            or not self.authorize_node(node)
            or not self.authorize_choice(choice)
            or not self.authorize_speaker(self.speaker_id, node_id)
        ):
            raise ValueError("Native dialogue choice was not offered")
        self.previous_choice_id = choice_id
        self.node_id = self.graph[(node_id, choice_id)]
        return b"native-choice"


class QuestNpcChoiceRouteTests(unittest.TestCase):
    def setUp(self):
        with gzip.open(
            ROOT / "database/protocol/npc-dialogues.json.gz", "rt"
        ) as source:
            native = json.load(source)
        self.node = next(row for row in native["nodes"] if row["id"] == 3206)
        self.row = {
            "actor_id": -2251799934981740,
            "reference_id": 1740,
            "map_id": 527,
            "instance_id": 0,
            "x": 109,
            "y": -20,
            "z": 0,
            "direction": 3,
            "dialogue_root": 1729,
            "action_ids": [158],
            "interaction_range": 4,
        }
        self.item = {
            "row": self.row,
            "quest_id": 2691,
            "activation_policy": "already_running",
            "graph": [[3206, 7954, 0]],
            "choice_routes": [
                {"node_id": 3206, "choice_id": 7954, "route": "zinit-reef-980"}
            ],
        }
        self.document = {"placements": [self.item], "activation_links": []}
        self.digest = conversation._digest(self.document)
        self.character = {
            "id": 7,
            "account_id": 2,
            "map_id": 527,
            "instance_id": 0,
            "x": 108,
            "y": -20,
            "z": 0,
        }

    def run_choice(self, session, choice_id=7954, callback=None):
        store = _Store()
        with (
            patch.object(
                quest_npc, "publication", return_value=(self.document, {}, {})
            ),
            patch.object(quest_npc, "_row", return_value=(self.row, self.item)),
            patch.object(quest_npc, "_owner"),
        ):
            return quest_npc.choose(
                store,
                2,
                "lease",
                self.character,
                session,
                struct.pack(">ii", 3206, choice_id),
                choice_entry=callback,
            )

    def test_route_callback_runs_once_only_after_accepted_native_choice(self):
        session = _Session(self.node, self.row["actor_id"])
        session.quest_publication_sha256 = self.digest
        calls = []

        def enter(db, store, character, proof):
            calls.append((db, store, character, proof))
            return {"instance_id": 123}

        result = self.run_choice(session, callback=enter)
        self.assertEqual(result["owned_entry"], {"instance_id": 123})
        self.assertIsNone(session.node_id)
        self.assertEqual(len(calls), 1)
        proof = calls[0][3]
        self.assertEqual(
            (
                proof["route_key"],
                proof["actor_id"],
                proof["reference_id"],
                proof["action_id"],
                proof["node_id"],
                proof["choice_id"],
            ),
            ("zinit-reef-980", self.row["actor_id"], 1740, 158, 3206, 7954),
        )
        self.assertEqual(proof["publication_sha256"], self.digest)
        self.assertEqual(
            proof["placement_sha256"], conversation.placement_signature(self.row)
        )

    def test_stale_or_unoffered_choice_never_calls_route_and_callback_failure_restores_session(
        self,
    ):
        for wrong_choice, stale in ((7955, False), (7954, True)):
            session = _Session(self.node, self.row["actor_id"])
            session.quest_publication_sha256 = self.digest
            if stale:
                session.node_id = 3212
            calls = []
            with self.subTest(choice=wrong_choice, stale=stale), self.assertRaises(
                ValueError
            ):
                self.run_choice(session, wrong_choice, lambda *args: calls.append(args))
            self.assertEqual(calls, [])

        session = _Session(self.node, self.row["actor_id"])
        session.quest_publication_sha256 = self.digest
        previous_authorizer = session.authorize_speaker
        with self.assertRaisesRegex(RuntimeError, "entry failed"):
            self.run_choice(
                session,
                callback=lambda *_args: (_ for _ in ()).throw(
                    RuntimeError("entry failed")
                ),
            )
        self.assertEqual(session.node_id, 3206)
        self.assertEqual(session.speaker_id, self.row["actor_id"])
        self.assertIs(session.authorize_speaker, previous_authorizer)

    def test_laura_site_arrival_uses_exact_native_exterior_approach_without_credit(
        self,
    ):
        declaration = {
            "node_id": 3287,
            "choice_id": 8107,
            "source_map_id": 1135,
            "source_object_id": 25523,
            "approach": {"x": -41, "y": 84, "z": -60},
            "direction": 3,
        }
        source = {
            "id": 25523,
            "map_id": 1135,
            "approach_positions": [dict(declaration["approach"])],
        }
        arrival = quest_npc.qualify_approach_arrival(source, declaration)
        self.assertEqual(
            arrival,
            {"map_id": 1135, "instance_id": 0, "x": -41, "y": 84, "z": -60},
        )
        for changed_source, changed_declaration in (
            (dict(source, id=2263), declaration),
            (dict(source, map_id=527), declaration),
            (dict(source, approach_positions=[]), declaration),
            (source, dict(declaration, approach={"x": -40, "y": 84, "z": -60})),
            (source, dict(declaration, direction=8)),
        ):
            with self.subTest(
                source=changed_source, declaration=changed_declaration
            ), self.assertRaises(ValueError):
                quest_npc.qualify_approach_arrival(changed_source, changed_declaration)


if __name__ == "__main__":
    unittest.main()
