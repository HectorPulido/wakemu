import struct
import unittest
from contextlib import contextmanager
from datetime import datetime, timezone
from unittest.mock import patch
from wakfu_server import ruel_hunt_npc as npc


class Store:
    def __init__(self, character):
        self.value = character

    @contextmanager
    def connection(self):
        yield self

    def execute(self, *args):
        return None

    def lock_character(self, *args, **kwargs):
        pass

    def character(self, *args):
        return dict(self.value)

    def now(self):
        return datetime(2026, 1, 1, tzinfo=timezone.utc)


class RuelNpcTest(unittest.TestCase):
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
            "running": [],
            "completed": [3974],
            "tracking": [],
            "recent": [],
            "completion_dates": {},
        }
        nodes = {
            4146: {
                "id": 4146,
                "criteria": "native",
                "choices": [
                    {"id": 10451, "criteria": "native"},
                    {"id": 10450, "criteria": ""},
                ],
            },
            4147: {
                "id": 4147,
                "criteria": "",
                "choices": [{"id": 10347, "criteria": ""}],
            },
            4141: {
                "id": 4141,
                "criteria": "",
                "choices": [{"id": 10341, "criteria": ""}],
            },
            4142: {
                "id": 4142,
                "criteria": "",
                "choices": [{"id": 10342, "criteria": ""}],
            },
            4143: {
                "id": 4143,
                "criteria": "",
                "choices": [{"id": 10343, "criteria": ""}],
            },
            4144: {
                "id": 4144,
                "criteria": "",
                "choices": [{"id": 10344, "criteria": ""}],
            },
            4150: {
                "id": 4150,
                "criteria": "",
                "choices": [{"id": 10351, "criteria": ""}],
            },
        }
        for target, kwargs in [
            (patch.object(npc, "_enabled", return_value=True), {}),
            (patch.object(npc, "_owner"), {}),
            (patch.object(npc.storage, "load_locked", return_value=self.state), {}),
            (
                patch.object(
                    npc.npc_dialogue, "catalog", return_value={"node_index": nodes}
                ),
                {},
            ),
        ]:
            target.start()
            self.addCleanup(target.stop)

    def test_offer_and_assignment_respects_session_and_records(self):
        session, packets = npc.begin(
            self.store,
            8,
            1,
            self.character,
            npc.ACTOR,
            npc.ACTION,
            character_provider=lambda: self.character,
        )
        self.assertEqual(12969, packets[-1][0])
        self.assertEqual(4146, session.node_id)
        with self.assertRaises(ValueError):
            npc.choose(
                self.store,
                8,
                1,
                self.character,
                session,
                struct.pack(">ii", 4146, 10452),
            )
        result = npc.choose(
            self.store, 8, 1, self.character, session, struct.pack(">ii", 4146, 10451)
        )
        self.assertEqual(4147, session.node_id)
        with patch.object(
            npc.storage, "record_event", return_value=True
        ) as receipt, patch.object(npc.storage, "store") as save:
            result = npc.choose(
                self.store,
                8,
                1,
                self.character,
                session,
                struct.pack(">ii", 4147, 10347),
            )
        after = save.call_args.args[2]
        self.assertEqual(1, len(after["running"]))
        self.assertEqual(after["running"], after["tracking"])
        self.assertEqual(after["running"][0], receipt.call_args.args[3]["quest_id"])
        self.assertIn(13312, [row[0] for row in result["packets"]])

    def test_no_prerequisite_no_offer_and_out_of_range(self):
        self.state["completed"] = []
        session, _ = npc.begin(
            self.store,
            8,
            1,
            self.character,
            npc.ACTOR,
            npc.ACTION,
            character_provider=lambda: self.character,
        )
        self.assertEqual(4142, session.node_id)
        npc.choose(
            self.store, 8, 1, self.character, session, struct.pack(">ii", 4142, 10342)
        )
        with patch.object(npc.storage, "record_event", return_value=True), patch.object(
            npc.storage, "store"
        ) as save, patch.object(npc, "drain_rewards", return_value=[]):
            npc.choose(
                self.store,
                8,
                1,
                self.character,
                session,
                struct.pack(">ii", 4143, 10343),
            )
        self.assertIn(3971, save.call_args.args[2]["running"])
        self.assertIn(3971, save.call_args.args[2]["tracking"])
        self.character["x"] = 50
        with self.assertRaises(ValueError):
            npc.begin(
                self.store,
                8,
                1,
                self.character,
                npc.ACTOR,
                npc.ACTION,
                character_provider=lambda: self.character,
            )

    def test_claim_story_reward_only_after_previous_mission(self):
        self.state["completed"] = [3973]
        session, _ = npc.begin(
            self.store,
            8,
            1,
            self.character,
            npc.ACTOR,
            npc.ACTION,
            character_provider=lambda: self.character,
        )
        self.assertEqual(4144, session.node_id)

        class Row:
            def __init__(self, value):
                self.value = value

            def fetchone(self):
                return self.value

        def execute(sql, *args):
            if "SELECT value FROM settings" in sql:
                return Row({"value": {"revision": "rev"}})
            if "native_quest_metadata_definitions" in sql:
                return Row({"data": {"native": {"d": 3974}}})
            return Row(None)

        def advance(state, definition, objective, **kwargs):
            self.assertEqual((3974, 8459), (definition["d"], objective))
            state["running"].remove(3974)
            state["completed"].append(3974)
            return state, [], [8459], [3974]

        with patch.object(self.store, "execute", side_effect=execute), patch.object(
            npc.mission_progress, "advance_objective", side_effect=advance
        ), patch.object(npc.storage, "record_event", return_value=True), patch.object(
            npc.storage, "store"
        ) as save, patch.object(
            npc, "drain_rewards", return_value=[]
        ):
            npc.choose(
                self.store,
                8,
                1,
                self.character,
                session,
                struct.pack(">ii", 4144, 10344),
            )
        self.assertIn(3974, save.call_args.args[2]["completed"])

    def test_native_sprite_has_animation_for_placement(self):
        import zipfile
        from pathlib import Path

        with zipfile.ZipFile(
            Path(__file__).resolve().parents[2]
            / "client/contents/animations/npcs/npcs.jar"
        ) as z:
            animation = z.read("192404573.anm")
        self.assertIn(
            f"{npc.placement()['direction']}_AnimStatique".encode(), animation
        )


if __name__ == "__main__":
    unittest.main()
