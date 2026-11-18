"""Focused qualification for weekly hunter presentation and acceptance."""
import gzip
import json
import csv
import struct
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from wakfu_server.maps import npc_dialogue, weekly_hunter_npc as hunter
from wakfu_server.objectives.environmental_recurring_offers import compile_hunter_offers


class WeeklyHunterNpcTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        root = Path(__file__).resolve().parents[1]
        protocol_path = root / "protocol/npc-dialogues.json.gz"
        if not protocol_path.is_file():
            protocol_path = root.parent / "database/protocol/npc-dialogues.json.gz"
        with gzip.open(protocol_path, "rt") as stream:
            nodes = json.load(stream)["nodes"]
        report = root.parent / "agents_docs/reports/parallel-readiness-20261021"
        with (report / "recurring-source-family-classification.csv").open() as stream:
            selected = {
                r["definition_id"]
                for r in csv.DictReader(stream)
                if r["family"] == "trade_hunt_contract_candidate"
            }
        with (report / "recurring-native-definitions.csv").open() as stream:
            ids = {
                int(r["definition_id"])
                for r in csv.DictReader(stream)
                if r["definition_id"] in selected
                and r["repeatable"] == "True"
                and r["calendar_period_seconds"] == "604800"
            }
        cls.native_offers = compile_hunter_offers(nodes, ids)

    def test_select_offers_chooses_highest_eligible_native_bracket(self):
        offers = [
            dict(
                definition_id=i.definition_id,
                version=2,
                node_id=i.node_id,
                choice_id=i.choice_id,
                minimum_level=i.minimum_level,
                category_id=i.category_id,
                criterion=i.criterion,
            )
            for i in self.native_offers.values()
        ]
        result = hunter.select_offers(offers, 100)
        expected_minimum = max(
            row["minimum_level"] for row in offers if row["minimum_level"] <= 100
        )
        self.assertTrue(result)
        self.assertEqual({row["minimum_level"] for row in result}, {expected_minimum})
        self.assertEqual(len(hunter.select_offers(offers, 21)), 2)
        self.assertEqual(len(hunter.select_offers(offers, 231)), 1)
        with self.assertRaisesRegex(ValueError, "No eligible"):
            hunter.select_offers(offers, 5)
        broken = dict(offers[0], minimum_level=offers[0]["minimum_level"] + 1)
        with self.assertRaisesRegex(ValueError, "differs from its native criterion"):
            hunter.select_offers([broken], 250)

    def test_magnum_masks_only_the_reconstructed_weekly_action(self):
        from test_npc_placements import EXPECTED, decode_spawn

        row = next(
            value for value in EXPECTED if value["reference_id"] == hunter.REFERENCE
        )
        normal = decode_spawn(
            __import__("wakfu_server.maps.npc_placements", fromlist=["spawn"]).spawn(
                dict(row, instance_id=0, enabled=True)
            )
        )
        enabled = decode_spawn(
            __import__("wakfu_server.maps.npc_placements", fromlist=["spawn"]).spawn(
                dict(row, instance_id=0, enabled=True, weekly_hunter_enabled=True)
            )
        )
        self.assertIn(hunter.ACTION, normal["masked_actions"])
        self.assertNotIn(hunter.ACTION, enabled["masked_actions"])
        self.assertEqual(
            enabled["masked_actions"],
            [x for x in normal["masked_actions"] if x != hunter.ACTION],
        )

    def test_recognizes_is_bound_to_actor_action_and_open_session(self):
        store = MagicMock()
        db = MagicMock()

        @contextmanager
        def connection():
            yield db

        store.connection = connection
        db.execute.return_value.fetchone.return_value = {
            "value": {
                "enabled": True,
                "actor_id": hunter.ACTOR,
                "action_id": hunter.ACTION,
            }
        }
        open_body = struct.pack(">qq", hunter.ACTOR, hunter.ACTION)
        self.assertTrue(hunter.recognizes(store, 13222, open_body, None))
        self.assertFalse(
            hunter.recognizes(
                store, 13222, struct.pack(">qq", hunter.ACTOR, hunter.ACTION + 1), None
            )
        )
        active = SimpleNamespace(weekly_hunter=True)
        self.assertTrue(hunter.recognizes(store, 12058, b"", active))
        self.assertFalse(hunter.recognizes(store, 12058, b"", None))

    def _acceptance_fixture(self, *, record_event=True):
        character = {
            "id": 41,
            "account_id": 7,
            "level": 100,
            "map_id": 12,
            "instance_id": 0,
            "x": 2,
            "y": 3,
            "z": 0,
        }
        row = {
            "actor_id": hunter.ACTOR,
            "map_id": 12,
            "instance_id": 0,
            "x": 2,
            "y": 3,
            "z": 0,
        }
        choices = self.native_offers
        chosen = max(
            (o for o in choices.values() if o.minimum_level <= character["level"]),
            key=lambda o: o.minimum_level,
        )
        offer = dict(
            definition_id=chosen.definition_id,
            version=2,
            node_id=chosen.node_id,
            choice_id=chosen.choice_id,
            minimum_level=chosen.minimum_level,
            category_id=chosen.category_id,
            criterion=chosen.criterion,
        )
        node = {
            "id": chosen.node_id,
            "criteria": "",
            "choices": [
                {"id": chosen.choice_id, "type": 5, "criteria": chosen.criterion}
            ],
        }
        session = npc_dialogue.DialogueSession(
            {chosen.node_id: node},
            {(chosen.node_id, chosen.choice_id): 0},
            authorize_node=lambda n: True,
            authorize_choice=lambda c: True,
        )
        session.open(
            chosen.node_id,
            hunter.ACTOR,
            lambda speaker, node_id: speaker == hunter.ACTOR,
        )
        session.weekly_hunter = True
        session.weekly_hunter_offers = {chosen.choice_id: offer}

        db = MagicMock()
        db.execute.return_value.fetchall.return_value = []
        db.execute.return_value.fetchone.return_value = None

        @contextmanager
        def connection():
            yield db

        store = MagicMock()
        store.connection = connection
        store.character.return_value = character
        store.lock_character.return_value = None
        contract = SimpleNamespace(period=lambda now: 3)
        patches = [
            patch.object(hunter, "_actor", return_value=row),
            patch.object(hunter, "_offers", return_value=[offer]),
            patch.object(hunter, "_owner"),
            patch.object(hunter.recurring, "synchronize", return_value=[]),
            patch.object(
                hunter.storage,
                "load_locked",
                return_value={"running": [], "completed": []},
            ),
            patch.object(
                hunter.recurring, "_load", return_value=(None, contract, None)
            ),
            patch.object(hunter.recurring, "_now", return_value=123),
            patch.object(hunter.storage, "record_event", return_value=record_event),
            patch.object(
                hunter.recurring,
                "accept_from_receipt",
                return_value={"packets": [(999, b"accepted")]},
            ),
        ]
        for p in patches:
            p.start()
            self.addCleanup(p.stop)
        return store, db, character, session, offer

    def test_native_offer_accepts_once_and_replay_is_rejected(self):
        store, _, character, session, offer = self._acceptance_fixture()
        body = struct.pack(">ii", offer["node_id"], offer["choice_id"])
        outcome = hunter.choose(store, 7, 1, character, session, body)
        self.assertEqual(outcome["definition_id"], offer["definition_id"])
        self.assertIn((999, b"accepted"), outcome["packets"])

        store, _, character, session, offer = self._acceptance_fixture(
            record_event=False
        )
        body = struct.pack(">ii", offer["node_id"], offer["choice_id"])
        with self.assertRaisesRegex(ValueError, "already recorded"):
            hunter.choose(store, 7, 1, character, session, body)

    def test_native_choice_accepts_daily_even_when_weekly_already_running(self):
        from wakfu_server.maps import daily_hunter_npc

        store, _, character, session, offer = self._acceptance_fixture()
        hunter.storage.load_locked.return_value = {
            "running": [offer["definition_id"]],
            "completed": [],
        }
        body = struct.pack(">ii", offer["node_id"], offer["choice_id"])
        with patch.object(daily_hunter_npc, "enabled", return_value=True), patch.object(
            daily_hunter_npc, "accept_for_choice", return_value=[(998, b"daily")]
        ) as accept:
            outcome = hunter.choose(store, 7, 1, character, session, body)
        self.assertIn((998, b"daily"), outcome["packets"])
        self.assertEqual(accept.call_args.args[3], offer)
        hunter.storage.record_event.assert_not_called()
        hunter.recurring.accept_from_receipt.assert_not_called()

    def test_choice_outside_offered_scope_does_not_accept(self):
        store, _, character, session, offer = self._acceptance_fixture()
        invalid = struct.pack(">ii", offer["node_id"], offer["choice_id"] + 1)
        with self.assertRaises(ValueError):
            hunter.choose(store, 7, 1, character, session, invalid)
        self.assertEqual(session.node_id, offer["node_id"])

    def test_acceptance_rechecks_authoritative_character_range(self):
        store, _, character, session, offer = self._acceptance_fixture()
        character["x"] = 30
        body = struct.pack(">ii", offer["node_id"], offer["choice_id"])
        with self.assertRaisesRegex(ValueError, "fuera de alcance"):
            hunter.choose(store, 7, 1, character, session, body)
        self.assertEqual(session.node_id, offer["node_id"])


if __name__ == "__main__":
    unittest.main()
