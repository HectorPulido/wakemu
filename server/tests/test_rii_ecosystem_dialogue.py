"""Rii return dialogue guards native objectives and completes child and parent."""
import copy
import struct
import unittest
from contextlib import nullcontext
from datetime import datetime, timezone
from unittest.mock import Mock, patch

from wakfu_server import rii_ecosystem_dialogue as dialogue
from test_npc_observed_dialogue import captured_row


class RiiReturnTests(unittest.TestCase):
    def setUp(self):
        self.row = captured_row(-1706442046308328, 5467, 1385, 12, 32, 1, 1, 5782, 1255)
        self.character = dict(
            id=1, account_id=2, map_id=1385, instance_id=0, x=12, y=32, z=1, level=10
        )
        self.state = dict(
            running=[5145, 5160],
            completed=[],
            objectives=[10578, 10579, 10597, 10598, 10599, 10600, 10607, 10615],
            tracking=[5145, 5160],
            completion_dates={},
            recent=[],
            variables={},
        )
        self.store = Mock()
        self.store.connection.return_value = nullcontext(Mock())
        self.store.character.return_value = self.character
        self.store.now.return_value = datetime(2026, 1, 1, tzinfo=timezone.utc)
        self.patchers = [
            patch.object(
                dialogue, "_snapshot", side_effect=lambda *a: copy.deepcopy(self.state)
            ),
            patch.object(dialogue.npc_world, "load_scene", return_value=[self.row]),
        ]
        for p in self.patchers:
            p.start()
            self.addCleanup(p.stop)

    def begin(self, count):
        with patch.object(dialogue, "_population", return_value=count):
            return dialogue.begin(
                self.store,
                lambda: self.character,
                lambda: [self.row],
                2,
                self.row["actor_id"],
                1255,
            )

    def test_population_roots_and_choices_use_real_conditions(self):
        for count, root, choices in [
            (0, 5799, (13360, 13361)),
            (20, 5762, (13337, 13339)),
            (80, 5762, (13337, 13339)),
            (81, 5800, (13364, 13365)),
        ]:
            with self.subTest(count=count):
                session, packet = self.begin(count)
                self.assertEqual(packet[1][:4], struct.pack(">i", root))
                self.assertEqual(
                    session.choose(root, choices[0]), (12218, struct.pack(">i", 5788))
                )
                self.assertTrue(
                    dialogue.recognizes(session, {"node_id": 5788, "choice_id": 13338})
                )
                session, _ = self.begin(count)
                self.state["objectives"].remove(10598)
                with self.assertRaises(ValueError):
                    session.choose(root, choices[1])
                self.state["objectives"].append(10598)

    def test_intro_stays_default_without_flag(self):
        self.state["objectives"].remove(10607)
        self.assertIsNone(self.begin(0))

    def test_information_path_remains_available_for_each_population_root(self):
        for count, root, question, leave in (
            (0, 5799, 13362, 13363),
            (20, 5762, 13319, 13350),
            (81, 5800, 13366, 13367),
        ):
            with self.subTest(root=root):
                original = copy.deepcopy(self.state)
                session, _ = self.begin(count)
                for node, choice, target in (
                    (root, question, 5792),
                    (5792, 13351, 5793),
                    (5793, 13352, 5794),
                    (5794, 13353, root),
                ):
                    self.assertEqual(
                        session.choose(node, choice), (12218, struct.pack(">i", target))
                    )
                self.assertEqual(
                    session.choose(root, leave), (12218, struct.pack(">i", 0))
                )
                self.assertEqual(original, self.state)

    def test_return_settles_child_and_parent_once(self):
        session, _ = self.begin(0)
        session.choose(5799, 13360)
        db = self.store.connection.return_value.__enter__()
        definitions = {
            5145: {
                "d": 5145,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjJ": [{"d": i, "ckc": "", "cke": ""} for i in (10597, 10579, 10578)]
                + [
                    {
                        "d": 10620,
                        "ckc": "IsAchievementObjectiveComplete(10597) and IsAchievementObjectiveComplete(10578) and IsAchievementObjectiveComplete(10579)",
                        "cke": "",
                    }
                ],
                "cjK": [],
            },
            5160: {
                "d": 5160,
                "native_class": "aJM",
                "aqb": False,
                "cjI": "",
                "cjJ": [
                    {"d": 10615, "ckc": "", "cke": ""},
                    {
                        "d": 10617,
                        "ckc": "IsAchievementObjectiveComplete(10615)",
                        "cke": "",
                    },
                    {"d": 10618, "ckc": "", "cke": ""},
                ],
                "cjK": [],
            },
        }
        from test_rii_ecosystem_activation import native_definitions

        for identity, native in native_definitions().items():
            if identity in definitions:
                definitions[identity].update(
                    {key: native[key] for key in ("cjU", "getDuration")}
                )
            else:
                for objective in native["cjJ"]:
                    objective.update(ckc="", cke="")
                native["cjK"] = []
                definitions[identity] = native
        db.execute.side_effect = lambda sql, args: Mock(
            fetchone=Mock(
                return_value={"data": {"native": definitions[args[0]]}}
                if "native_quest_metadata" in sql
                else {"id": 2}
            )
        )
        from wakfu_server.achievements import storage

        with patch.object(
            storage, "load_locked", side_effect=lambda *a: copy.deepcopy(self.state)
        ), patch.object(
            storage,
            "store",
            side_effect=lambda db, ident, state: setattr(
                self, "state", copy.deepcopy(state)
            ),
        ), patch.object(
            storage, "record_event", return_value=True
        ), patch(
            "wakfu_server.achievements.rii_starter_seed.grant_if_missing",
            return_value=[],
        ), patch(
            "wakfu_server.achievements.service._owner"
        ), patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ):
            result = dialogue.choose(
                self.store,
                2,
                1,
                self.character,
                session,
                {"node_id": 5788, "choice_id": 13338},
            )
        self.assertEqual(result["packet"], (12218, struct.pack(">i", 0)))
        self.assertIn(5145, self.state["completed"])
        self.assertIn(10620, self.state["objectives"])
        self.assertIn(10617, self.state["objectives"])
        self.assertNotIn(5145, self.state["running"])
        self.assertIn(5155, self.state["running"])
        self.assertNotIn(5156, self.state["running"])
        self.assertTrue(any(code == 13832 for code, _ in result["packets"]))

        session, _ = self.begin(0)
        session.choose(5799, 13361)
        with patch.object(
            storage, "load_locked", side_effect=lambda *a: copy.deepcopy(self.state)
        ), patch.object(
            storage,
            "store",
            side_effect=lambda db, ident, state: setattr(
                self, "state", copy.deepcopy(state)
            ),
        ), patch.object(
            storage, "record_event", return_value=True
        ), patch(
            "wakfu_server.achievements.rii_starter_seed.grant_if_missing",
            return_value=[],
        ), patch(
            "wakfu_server.achievements.service._owner"
        ), patch(
            "wakfu_server.achievements.service.drain_rewards", return_value=[]
        ):
            dialogue.choose(
                self.store,
                2,
                1,
                self.character,
                session,
                {"node_id": 5789, "choice_id": 13340},
            )
        self.assertIn(5155, self.state["completed"])
        self.assertIn(5156, self.state["running"])
        self.assertNotIn(5155, self.state["running"])


if __name__ == "__main__":
    unittest.main()
