import struct
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch

from wakfu_server.maps import ruel_investigation_npc as investigation
from wakfu_server.achievements import ruel_story


class Row:
    def __init__(self, value=None, values=None):
        self.value = value
        self.values = values or []

    def fetchone(self):
        return self.value

    def fetchall(self):
        return list(self.values)


class Database:
    def __init__(self):
        self.events = {}

    def execute(self, sql, args=()):
        if "SELECT event_key FROM character_achievement_events" in sql:
            keys = args[1]
            return Row(values=[{"event_key": k} for k in keys if k in self.events])
        if "SELECT value FROM settings" in sql:
            return Row({"value": {"revision": "rev"}})
        if "native_quest_metadata_definitions" in sql:
            return Row({"data": {"native": {"d": 3973}}})
        return Row()


class Store:
    def __init__(self, character):
        self.value = character
        self.db = Database()

    @contextmanager
    def connection(self):
        yield self.db

    def lock_character(self, *args, **kwargs):
        pass

    def character(self, *args):
        return dict(self.value)

    def now(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class Session:
    def __init__(self, actor, root, graph):
        self.speaker_id = actor
        self.node_id = root
        self.graph = graph
        self.authorize_speaker = None

    def choose(self, node_id, choice_id):
        self.node_id = self.graph[(node_id, choice_id)]
        return None


class RuelStoryProgressTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 7,
            "account_id": 8,
            "level": 35,
            "map_id": 527,
            "instance_id": 0,
            "x": -22,
            "y": 3,
            "z": 0,
        }
        self.store = Store(self.character)
        self.state = {
            "variables": {},
            "objectives": [],
            "running": [3973],
            "completed": [],
            "tracking": [3973],
            "recent": [],
            "completion_dates": {},
        }

    def test_all_three_suspect_receipts_complete_investigation_once(self):
        advances = []

        def advance(state, definition, objective, **kwargs):
            advances.append((definition["d"], objective))
            state = dict(state, running=[], completed=[3973])
            return state, [], [8458], [3973]

        with patch.object(investigation, "_owner"), patch.object(
            investigation.storage, "load_locked", return_value=self.state
        ), patch.object(
            investigation.npc_world, "nearby", return_value=True
        ), patch.object(
            investigation.storage,
            "record_event",
            side_effect=lambda db, cid, key, fact: db.events.setdefault(key, fact)
            is not None,
        ), patch.object(
            investigation.storage, "store"
        ) as save, patch.object(
            investigation, "drain_rewards", return_value=[]
        ), patch.object(
            investigation.mission_progress, "advance_objective", side_effect=advance
        ):
            for actor, (
                reference,
                _action,
                _position,
                root,
                graph,
            ) in investigation.SUSPECTS.items():
                session = Session(actor, root, graph)
                for (node_id, choice_id), _next in graph.items():
                    if _next == 0:
                        result = investigation.choose(
                            self.store,
                            8,
                            1,
                            self.character,
                            session,
                            struct.pack(">ii", node_id, choice_id),
                        )
                    else:
                        # The dialogue can be replayed through a path; only its terminal edge records an interview.
                        session.choose(node_id, choice_id)
                self.assertIn(f"ruel-investigation:{reference}", self.store.db.events)

        self.assertEqual([(3973, 8458)], advances)
        self.assertEqual([3973], save.call_args.args[2]["completed"])

    def test_unowned_phorreur_victory_does_not_advance_trace(self):
        event = {"fight_id": 901, "original_monsters": [(-44, ruel_story.PHORREUR)]}
        db = Database()
        db.execute = lambda sql, args=(): Row(
            {"value": {"enabled": True, "revision": "rev"}}
            if "settings" in sql
            else {"data": {"native": {"d": 3972}}}
            if "native_quest_metadata_definitions" in sql
            else None
        )
        with patch.object(
            ruel_story.storage,
            "load_locked",
            return_value=dict(self.state, running=[3972]),
        ), patch.object(ruel_story.mission_progress, "advance_objective") as advance:
            packets = ruel_story.settle_trace_fight(
                db, self.store, dict(self.character), event
            )
        self.assertEqual([], packets)
        advance.assert_not_called()

    def test_owned_phorreur_victory_counts_battle_objective(self):
        actor_id = -99
        event = {
            "fight_id": 902,
            "original_monsters": [(actor_id, ruel_story.PHORREUR)],
        }
        db = Database()

        def execute(sql, args=()):
            if "SELECT payload FROM character_achievement_events" in sql:
                return Row(
                    {
                        "payload": {
                            "kind": "reconstructed_ruel_phorreur_spawn_v1",
                            "actor_id": actor_id,
                            "reference": ruel_story.PHORREUR,
                            "owner": 7,
                        }
                    }
                )
            if "SELECT value FROM settings" in sql:
                return Row({"value": {"enabled": True, "revision": "rev"}})
            if "native_quest_metadata_definitions" in sql:
                return Row({"data": {"native": {"d": 3972}}})
            return Row()

        db.execute = execute

        def advance(state, definition, objective, **kwargs):
            self.assertEqual((3972, 8452), (definition["d"], objective))
            return dict(state, objectives=[8452]), [], [8452], []

        with patch.object(
            ruel_story.storage,
            "load_locked",
            return_value=dict(self.state, running=[3972]),
        ), patch.object(
            ruel_story.storage, "record_event", return_value=True
        ) as receipt, patch.object(
            ruel_story.storage, "store"
        ) as save, patch.object(
            ruel_story, "drain_rewards", return_value=[]
        ), patch.object(
            ruel_story.mission_progress, "advance_objective", side_effect=advance
        ):
            packets = ruel_story.settle_trace_fight(
                db, self.store, dict(self.character), event
            )

        self.assertTrue(packets)
        self.assertEqual("ruel-trace-fight:902", receipt.call_args.args[2])
        self.assertEqual([8452], save.call_args.args[2]["objectives"])

    def test_movement_visits_only_the_next_trace(self):
        trace_state = dict(self.state, running=[3972], objectives=[8452])
        character = dict(self.character, map_id=527, x=-74, y=-75, z=0)
        self.assertEqual(8453, ruel_story.matching_trace(character))

        def execute(sql, args=()):
            if "SELECT value FROM settings" in sql:
                return Row({"value": {"enabled": True, "revision": "rev"}})
            if "native_quest_metadata_definitions" in sql:
                return Row({"data": {"native": {"d": 3972}}})
            return Row()

        def advance(state, definition, objective, **kwargs):
            self.assertEqual((3972, 8453), (definition["d"], objective))
            after = dict(state, objectives=[8452, 8453])
            return after, [], [8453], []

        self.store.db.execute = execute
        with patch.object(ruel_story, "_owner"), patch.object(
            ruel_story.storage, "load_locked", return_value=trace_state
        ), patch.object(
            ruel_story.storage, "record_event", return_value=True
        ), patch.object(
            ruel_story.storage, "store"
        ) as save, patch.object(
            ruel_story, "drain_rewards", return_value=[]
        ), patch.object(
            ruel_story.mission_progress, "advance_objective", side_effect=advance
        ):
            self.assertEqual([], ruel_story.visit_trace(self.store, 8, 1, character))
            packets = ruel_story.visit_trace(
                self.store, 8, 1, character, objective=8453
            )
        self.assertTrue(packets)
        self.assertEqual([8452, 8453], save.call_args.args[2]["objectives"])

    def test_observing_trace_requires_owned_progress_and_exact_action(self):
        from wakfu_server import world_static

        character = dict(self.character, x=-74, y=-75, z=0)
        self.store.value = character
        body = struct.pack(">qHH", 29314, 0, 0)
        self.assertTrue(ruel_story.recognizes_trace(527, body))
        self.assertFalse(
            ruel_story.recognizes_trace(527, struct.pack(">qHH", 29314, 1, 0))
        )
        interaction = {
            "type": "GenericActivableInteractiveElement",
            "x": -74,
            "y": -75,
            "z": 0,
        }
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.object(ruel_story, "_owner"), patch.object(
            world_static, "interaction", return_value=interaction
        ), patch.object(
            ruel_story.storage,
            "load_locked",
            return_value=dict(self.state, running=[3972], objectives=[8452]),
        ), patch.object(
            ruel_story, "visit_trace", return_value=[(13312, b"quest")]
        ) as settle:
            result = ruel_story.interact_trace(
                self.store, None, 8, 1, character, body, loaded=True, blocked=False
            )
        self.assertEqual([(13312, b"quest")], result["packets"])
        self.assertEqual(8453, settle.call_args.kwargs["objective"])

        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.object(ruel_story, "_owner"), patch.object(
            world_static, "interaction", return_value=interaction
        ), patch.object(
            ruel_story.storage,
            "load_locked",
            return_value=dict(self.state, running=[3972], objectives=[]),
        ), patch.object(
            ruel_story, "visit_trace"
        ) as settle:
            result = ruel_story.interact_trace(
                self.store, None, 8, 1, character, body, loaded=True, blocked=False
            )
        self.assertEqual([], result["packets"])
        settle.assert_not_called()

    def test_first_observation_spawns_encounter_without_completing_objective(self):
        from wakfu_server import world_static

        character = dict(self.character, x=-72, y=5, z=0)
        self.store.value = character
        with patch("wakfu_server.paid_containers._leased_owner"), patch(
            "wakfu_server.environment_interactions._guard"
        ), patch.object(ruel_story, "_owner"), patch.object(
            world_static,
            "interaction",
            return_value={
                "type": "GenericActivableInteractiveElement",
                "x": -72,
                "y": 5,
                "z": 0,
            },
        ), patch.object(
            ruel_story.storage,
            "load_locked",
            return_value=dict(self.state, running=[3972], objectives=[]),
        ), patch.object(
            ruel_story, "spawn_trace_fight", return_value=(12608, b"encounter")
        ) as spawn, patch.object(
            ruel_story, "visit_trace"
        ) as settle:
            result = ruel_story.interact_trace(
                self.store,
                None,
                8,
                1,
                character,
                struct.pack(">qHH", 29306, 0, 0),
                loaded=True,
                blocked=False,
            )
        self.assertEqual((12608, b"encounter"), result["scene_packet"])
        spawn.assert_called_once()
        settle.assert_not_called()


if __name__ == "__main__":
    unittest.main()
