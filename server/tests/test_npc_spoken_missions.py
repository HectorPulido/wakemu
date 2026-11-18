"""Reviewed NPC speech advances only its active native objective."""

import unittest
from contextlib import contextmanager
import json
from pathlib import Path
from copy import deepcopy
from unittest.mock import patch

from wakfu_server import quest_npc
from psycopg.types.json import Jsonb
from postgres_case import PostgresCase
from wakfu_server.achievements import (
    conversation,
    mission_toolkit,
    npc_spoken_missions,
    storage,
)


class _DB:
    def execute(self, *_args, **_kwargs):
        return self


class _Store:
    def __init__(self):
        self.db_calls = 0

    @contextmanager
    def connection(self):
        self.db_calls += 1
        yield _DB()

    def lock_character(self, *_args, **_kwargs):
        pass

    def character(self, account_id, character_id, _db):
        return {
            "id": character_id,
            "account_id": account_id,
            "map_id": 527,
            "instance_id": 0,
            "x": 10,
            "y": 20,
            "z": 0,
        }


class _Session:
    def __init__(self, actor_id, digest):
        self.quest_publication_sha256 = digest
        self.quest_conversation_actor_id = actor_id
        self.speaker_id = actor_id
        self.node_id = 10

    def authorize_speaker(self, speaker_id, node_id):
        return speaker_id == self.speaker_id and node_id == self.node_id


class NpcSpokenMissionTests(unittest.TestCase):
    def setUp(self):
        self.actor_id = -2251799934992019
        self.row = {
            "actor_id": self.actor_id,
            "reference_id": 1322,
            "map_id": 527,
            "instance_id": 0,
            "x": 10,
            "y": 20,
            "z": 0,
            "direction": 0,
            "dialogue_root": 10,
            "action_ids": [431],
            "interaction_range": 2,
        }
        self.spoken = {
            "quest_id": 2675,
            "objective_id": 8330,
            "action_ids": [431],
            "evidence": "Reviewed native conversation event for objective 8330.",
        }
        self.item = {
            "row": self.row,
            "quest_id": 2675,
            "activation_policy": "already_running",
            "graph": [],
            "spoken_objectives": [self.spoken],
        }
        self.document = {"placements": [self.item]}
        self.digest = conversation._digest(self.document)
        self.state = {
            "running": [2675],
            "active": [2675],
            "active_periods": {},
            "completed": [],
            "objectives": [],
            "variables": {},
            "completion_dates": {},
        }

    def call(self, *, session=None, row=None, action_id=431, state=None):
        store = _Store()
        session = session or _Session(self.actor_id, self.digest)
        row = row or self.row
        with (
            patch.object(
                quest_npc, "publication", return_value=(self.document, {}, {})
            ),
            patch.object(quest_npc, "_row", return_value=(self.row, self.item)),
            patch.object(quest_npc, "_nearby_placement", return_value=True),
            patch("wakfu_server.achievements.npc_spoken_missions._owner"),
            patch(
                "wakfu_server.achievements.storage.load_locked",
                return_value=state or self.state,
            ),
        ):
            result = npc_spoken_missions.on_open(
                store,
                7,
                "lease",
                {"id": 41, "account_id": 7},
                row,
                action_id,
                session,
                self.digest,
            )
        return store, result

    def test_authenticated_running_native_speech_settles_exact_objective_and_packets(
        self,
    ):
        packets = [(13405, b"objective-update")]
        with patch(
            "wakfu_server.achievements.mission_toolkit.settle", return_value=packets
        ) as settle:
            store, result = self.call()
        self.assertEqual(result, packets)
        self.assertEqual(store.db_calls, 1)
        self.assertEqual(settle.call_args.kwargs["kind"], "npc_spoken")
        self.assertEqual(settle.call_args.kwargs["reference"], 8330)
        self.assertTrue(
            settle.call_args.kwargs["token"].startswith("native-npc-spoken:")
        )

    def test_stale_open_wrong_action_or_changed_placement_cannot_settle(self):
        for session, row, action in (
            (_Session(self.actor_id, "f" * 64), self.row, 431),
            (_Session(self.actor_id + 1, self.digest), self.row, 431),
            (_Session(self.actor_id, self.digest), self.row, 999),
            (_Session(self.actor_id, self.digest), dict(self.row, x=11), 431),
        ):
            with self.subTest(action=action, actor=session.speaker_id), patch(
                "wakfu_server.achievements.mission_toolkit.settle"
            ) as settle:
                with self.assertRaises(ValueError):
                    self.call(session=session, row=row, action_id=action)
                settle.assert_not_called()

    def test_inactive_or_already_completed_objective_is_inert(self):
        completed_objective = dict(self.state, objectives=[8330])
        inactive = dict(self.state, running=[], active=[])
        for state in (completed_objective, inactive):
            with self.subTest(
                state=state["objectives"], running=state["running"]
            ), patch("wakfu_server.achievements.mission_toolkit.settle") as settle:
                _store, result = self.call(state=state)
                self.assertEqual(result, [])
                settle.assert_not_called()

    def test_begin_calls_spoken_adapter_only_after_session_open_metadata_is_set(self):
        events = []

        class OpenedSession:
            def __init__(self, *_args, **_kwargs):
                self.speaker_id = None
                self.node_id = None

            def open(self, root, actor_id, _authorize):
                self.speaker_id = actor_id
                self.node_id = root
                events.append("open")
                return b"native-open"

        with (
            patch.object(
                quest_npc, "publication", return_value=(self.document, {}, {})
            ),
            patch.object(quest_npc, "_row", return_value=(self.row, self.item)),
            patch.object(quest_npc, "_nearby_placement", return_value=True),
            patch.object(quest_npc, "_owner"),
            patch.object(
                quest_npc.npc_dialogue, "catalog", return_value={"node_index": {}}
            ),
            patch.object(quest_npc.npc_dialogue, "DialogueSession", OpenedSession),
            patch.object(quest_npc, "_criterion", return_value=True),
            patch.object(
                npc_spoken_missions,
                "on_open",
                side_effect=lambda _store, _account, _generation, _character, row, _action, session, digest: (
                    events.append("spoken")
                    or self.assertEqual(events, ["open", "spoken"])
                    or self.assertEqual(session.quest_publication_sha256, digest)
                    or self.assertEqual(
                        session.quest_conversation_actor_id, row["actor_id"]
                    )
                    or [(13405, b"objective-update")]
                ),
            ),
        ):
            session, packets = quest_npc.begin(
                _Store(),
                7,
                "lease",
                {"id": 41, "account_id": 7},
                self.actor_id,
                431,
                character_provider=lambda: {"id": 41, "account_id": 7},
                rows_provider=lambda: [self.row],
            )
        self.assertEqual(events, ["open", "spoken"])
        self.assertEqual(packets, [b"native-open", (13405, b"objective-update")])
        self.assertEqual(session.quest_conversation_actor_id, self.actor_id)


class NpcSpokenMissionPostgresTests(PostgresCase):
    def test_native_8330_guard_then_spoken_8331_advances_once_with_hud_packets(self):
        fixture = json.loads(
            (
                Path(__file__).parent
                / "fixtures/native_quest_2676_spoken_objectives.json"
            ).read_text()
        )
        definition = fixture["definition"]
        account = self.store.register("spoken-native", "isolated-test-password")["id"]
        character = self.store.create_character(account, "Spoken Native")
        generation = self.store.begin_session(account)
        self.store.select_character(account, generation, character["id"])
        with self.store.connection() as db:
            db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
            db.execute(
                "UPDATE characters SET map_id=527,instance_id=0 WHERE id=%s",
                (character["id"],),
            )
            revision = "b" * 64
            db.execute(
                "INSERT INTO native_quest_metadata_releases(revision,source_sha256,source_export,definition_count) VALUES(%s,%s,%s,%s)",
                (
                    revision,
                    Jsonb({"fixture": revision}),
                    b"native 2676 spoken objective",
                    1,
                ),
            )
            db.execute(
                "INSERT INTO native_quest_metadata_definitions(revision,definition_id,data) VALUES(%s,%s,%s)",
                (revision, 2676, Jsonb({"native": definition})),
            )
            profile = {
                "version": 1,
                "id": "npc-spoken-8331-test",
                "evidence": [
                    "Native 2676 objective 8331 requires prior objective 8330."
                ],
                "bindings": [
                    {
                        "id": "spoken-8331",
                        "quest_id": 2676,
                        "objective_id": 8331,
                        "event": {"kind": "npc_spoken", "reference": 8331},
                        "count": "operation",
                        "maps": [527],
                        "instances": [0],
                    }
                ],
                "links": [],
                "activations": [],
            }
            mission_toolkit.install(db, profile, activate=True)
            state = storage.load_locked(db, character["id"])
            state["running"] = [2676]
            state["completed"] = [2675]
            state["active"] = [2676]
            state["active_unknown"] = []
            storage.store(db, character["id"], state)

        actor_id = -2251799934992019
        row = {
            "actor_id": actor_id,
            "reference_id": 1322,
            "map_id": 527,
            "instance_id": 0,
            "x": 0,
            "y": 0,
            "z": 0,
            "direction": 0,
            "dialogue_root": 10,
            "action_ids": [431],
            "interaction_range": 2,
        }
        item = {
            "row": row,
            "quest_id": 2676,
            "spoken_objectives": [
                {
                    "quest_id": 2676,
                    "objective_id": 8331,
                    "action_ids": [431],
                    "evidence": "Reviewed native NPC opening for objective 8331.",
                }
            ],
        }
        document = {"placements": [item]}
        digest = conversation._digest(document)

        class Session:
            quest_publication_sha256 = digest
            quest_conversation_actor_id = actor_id
            speaker_id = actor_id
            node_id = 10

            @staticmethod
            def authorize_speaker(speaker_id, node_id):
                return (speaker_id, node_id) == (actor_id, 10)

        session = Session()
        with (
            patch.object(
                quest_npc,
                "publication",
                return_value=(document, {2676: definition}, {}),
            ),
            patch.object(quest_npc, "_row", return_value=(row, item)),
            patch.object(quest_npc, "_nearby_placement", return_value=True),
        ):
            # The native ckc on 8331 is not met yet, so the planner must not
            # advance it or persist a producer receipt.
            with self.store.connection() as db:
                before = storage.load_locked(db, character["id"])
            self.assertNotIn(8331, before["objectives"])
            first = npc_spoken_missions.on_open(
                self.store, account, generation, character, row, 431, session, digest
            )
            with self.store.connection() as db:
                after = storage.load_locked(db, character["id"])
            self.assertEqual(first, [])
            self.assertNotIn(8331, after["objectives"])
            with self.store.connection() as db:
                db.execute("SELECT id FROM accounts WHERE id=%s FOR UPDATE", (account,))
                after = storage.load_locked(db, character["id"])
                after["objectives"] = [8330]
                storage.store(db, character["id"], after)
            packets = npc_spoken_missions.on_open(
                self.store, account, generation, character, row, 431, session, digest
            )
            with self.store.connection() as db:
                settled = storage.load_locked(db, character["id"])
            self.assertIn(8331, settled["objectives"])
            self.assertTrue(packets)
            replay = npc_spoken_missions.on_open(
                self.store, account, generation, character, row, 431, session, digest
            )
            self.assertEqual(replay, [])
            with self.store.connection() as db:
                self.assertEqual(
                    storage.load_locked(db, character["id"])["objectives"].count(8331),
                    1,
                )


class NpcSpokenPublicationTests(unittest.TestCase):
    source = (
        Path(__file__).resolve().parents[1]
        / "wakfu_server/maps/native_quest_conversation_contracts.json"
    )
    native_definition = (
        Path(__file__).resolve().parent
        / "fixtures/native_quest_2676_spoken_objectives.json"
    )

    def test_spoken_only_publication_requires_native_objective_action_and_source(self):
        document = json.loads(self.source.read_text())
        placement = next(
            item
            for item in document["placements"]
            if any(
                s.get("quest_id") == 2676 and s.get("objective_id") == 8331
                for s in item.get("spoken_objectives", [])
            )
        )
        document["placements"] = [deepcopy(placement)]
        document["recurring_deliveries"] = []
        native_definition = json.loads(self.native_definition.read_text())["definition"]
        published_definition = next(
            item for item in document["definitions"] if item["d"] == 2676
        )
        self.assertEqual(published_definition, native_definition)
        rows_by_node = {}
        for node_id, choice_id, _target in placement["graph"]:
            rows_by_node.setdefault(node_id, set()).add(choice_id)
        native = {
            "speakers": [{"ref": 3275, "actions": [{"id": 596}]}],
            "node_index": {
                identity: {
                    "id": identity,
                    "criteria": "",
                    "choices": [{"id": choice} for choice in choices],
                }
                for identity, choices in rows_by_node.items()
            },
        }

        class DB:
            def __init__(self, value):
                self.value = value

            def execute(self, *_args):
                return self

            def fetchone(self):
                return {"value": self.value}

        def publish(candidate):
            with (
                patch.object(
                    quest_npc,
                    "source_contract_digest",
                    return_value=conversation._digest(candidate),
                ),
                patch.object(quest_npc.npc_dialogue, "catalog", return_value=native),
            ):
                return quest_npc.publication(DB(candidate))

        accepted = publish(document)
        self.assertEqual(accepted[0]["placements"], [placement])
        self.assertEqual(
            placement["spoken_objectives"],
            [
                {
                    "quest_id": 2676,
                    "objective_id": 8331,
                    "action_ids": [596],
                    "evidence": placement["spoken_objectives"][0]["evidence"],
                }
            ],
        )

        cases = []
        unbound_actor = deepcopy(document)
        unbound_actor["placements"][0].pop("spoken_objectives")
        cases.append(("unbound actor", unbound_actor))
        malformed_action = deepcopy(document)
        malformed_action["placements"][0]["spoken_objectives"][0]["action_ids"] = [597]
        cases.append(("malformed action", malformed_action))
        foreign_objective = deepcopy(document)
        foreign_objective["placements"][0]["spoken_objectives"][0][
            "objective_id"
        ] = 999999
        cases.append(("foreign objective", foreign_objective))
        for label, candidate in cases:
            with self.subTest(label=label), self.assertRaises(ValueError):
                publish(candidate)


if __name__ == "__main__":
    unittest.main()
