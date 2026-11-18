"""Conversation completion settles native rewards and active parent links."""

import hashlib
import json
from pathlib import Path
import unittest

from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import conversation, mission_toolkit, storage


ROOT = Path(__file__).resolve().parents[1]
NATIVE_FIXTURE = ROOT / "tests/fixtures/native_mount_precursor_definitions.json"
CONVERSATION_CONTRACT = (
    ROOT / "wakfu_server/maps/native_quest_conversation_contracts.json"
)
MOUNT_PROFILE = (
    ROOT / "wakfu_server/achievements/mission_profiles/astrub-mount-books.json"
)


class OfferedConversation:
    def __init__(self, actor_id, node_id, choice_id):
        self.speaker_id = actor_id
        self.node_id = node_id
        self.graph = {(node_id, choice_id)}

    def quest_nearby(self, _character, _row):
        return True

    def authorize_speaker(self, actor_id, node_id):
        return (actor_id, node_id) == (self.speaker_id, self.node_id)

    def _node(self, node_id):
        if node_id != self.node_id:
            raise ValueError("Unexpected native dialogue node")
        return {"choices": [{"id": next(iter(self.graph))[1]}]}

    def authorize_choice(self, choice):
        return choice["id"] in {identity for _, identity in self.graph}


class ConversationMissionLinkPostgresTests(PostgresCase):
    def test_conversation_settlement_awards_book_and_immediately_advances_parent_once(
        self,
    ):
        account = self.store.register(
            "conversation-mount-link", "isolated-test-password"
        )["id"]
        character = self.store.create_character(account, "Conversation Mount")

        fixture = json.loads(NATIVE_FIXTURE.read_text())
        definitions = {
            row["d"]: row
            for row in fixture["definitions"]
            if row["d"] in {2015, 2016, 2048}
        }
        # The profile contains a sibling link that this case does not activate.
        # Keep that native identity present while limiting the fixture to the
        # exact conversation and parent path under test.
        definitions[2017] = {
            "d": 2017,
            "native_class": "aJM",
            "aqb": False,
            "cjI": "",
            "cjJ": [{"d": 45017, "ckc": "", "cke": "", "ckf": []}],
            "cjK": [],
            "cjU": 0,
            "cjL": 0,
            "getDuration": 0,
        }
        contract = json.loads(CONVERSATION_CONTRACT.read_text())
        placement = next(
            value["row"]
            for value in contract["placements"]
            if value["row"]["reference_id"] == 2775
        )
        binding_data = next(
            value
            for value in contract["bindings"]
            if value["quest_id"] == 2016
            and value["objective_id"] == 4140
            and value["node_id"] == 2297
            and value["choice_id"] == 6541
        )
        binding = conversation.QualifiedConversation(**binding_data)
        session = OfferedConversation(placement["actor_id"], 2297, 6541)
        revision = hashlib.sha256(
            (str(account) + ":mount-conversation-test").encode()
        ).hexdigest()

        with self.store.connection() as db:
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) "
                "VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb(
                        {
                            "fixture": hashlib.sha256(
                                NATIVE_FIXTURE.read_bytes()
                            ).hexdigest()
                        }
                    ),
                    NATIVE_FIXTURE.read_bytes(),
                    len(definitions),
                ),
            )
            for identity, definition in definitions.items():
                db.execute(
                    "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) "
                    "VALUES(%s,%s,%s)",
                    (revision, identity, Jsonb({"native": definition})),
                )
            db.execute(
                "INSERT INTO world_dialogue_npcs "
                "(actor_id,reference_id,map_id,instance_id,x,y,z,direction,dialogue_root,action_ids,interaction_range,enabled,provenance) "
                "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    placement["actor_id"],
                    placement["reference_id"],
                    placement["map_id"],
                    placement["instance_id"],
                    placement["x"],
                    placement["y"],
                    placement["z"],
                    placement["direction"],
                    placement["dialogue_root"],
                    Jsonb(placement["action_ids"]),
                    placement["interaction_range"],
                    placement["enabled"],
                    placement["provenance"],
                ),
            )
            profile = json.loads(MOUNT_PROFILE.read_text())
            mission_toolkit.install(db, profile, activate=True)

            db.execute(
                "UPDATE characters SET level=35,map_id=%s,instance_id=0,x=%s,y=%s,z=%s WHERE id=%s",
                (
                    placement["map_id"],
                    placement["x"],
                    placement["y"],
                    placement["z"],
                    character["id"],
                ),
            )
            owner = self.store.character(account, character["id"], db)
            state = storage.load_locked(db, character["id"])
            state["running"] = [2015, 2016]
            state["completed"] = []
            state["objectives"] = [4076, 4079, 4084]
            state["tracking"] = [2015, 2016]
            storage.store(db, character["id"], state)

            result = conversation.settle(
                db,
                self.store,
                owner,
                session,
                binding,
                definitions[2016],
                node_id=2297,
                choice_id=6541,
            )
            self.assertTrue(result["applied"])
            self.assertEqual(result["completed"], [2016])
            self.assertIn(
                13832,
                [
                    packet[0]
                    for packet in result["packets"]
                    if isinstance(packet, tuple)
                ],
            )

            after = storage.load_locked(db, character["id"])
            self.assertIn(2016, after["completed"])
            self.assertIn(4077, after["objectives"])
            book = db.execute(
                "SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=18629",
                (character["id"],),
            ).fetchone()
            self.assertIsNotNone(book)
            self.assertEqual(book["quantity"], 1)

            replay_packets = mission_toolkit.settle_completions(
                db, self.store, owner, [2016]
            )
            self.assertEqual(replay_packets, [])
            after_replay = storage.load_locked(db, character["id"])
            self.assertEqual(after_replay["objectives"].count(4077), 1)
            self.assertEqual(
                db.execute(
                    "SELECT quantity FROM inventory_items WHERE character_id=%s AND reference=18629",
                    (character["id"],),
                ).fetchone()["quantity"],
                1,
            )
            reward = db.execute(
                "SELECT delivered_at FROM character_achievement_reward_outbox "
                "WHERE character_id=%s AND achievement_id=2016 AND reward_key='3467'",
                (character["id"],),
            ).fetchone()
            self.assertIsNotNone(reward)
            self.assertIsNotNone(reward["delivered_at"])


if __name__ == "__main__":
    unittest.main()
