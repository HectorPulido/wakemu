import struct
import unittest
from unittest.mock import patch
from wakfu_server.achievements import incarnam_tutorial
from wakfu_server.intro_cinematic import private_instance_id
from wakfu_server import ecology_mobs


class IncarnamWalkAndEcologyTests(unittest.TestCase):
    def setUp(self):
        self.character = {
            "id": 217,
            "map_id": 1361,
            "instance_id": private_instance_id(217),
            "x": 13,
            "y": -18,
            "z": -16,
        }
        self.state = {"running": [5135]}

    def test_walk_guide_crosses_all_native_cells_in_order_and_resume(self):
        points = [
            (4, -1, -4),
            (5, 0, -4),
            (11, 0, -16),
            (12, 0, -16),
            (12, -8, -16),
            (12, -9, -16),
        ]
        path = [dict(zip(("x", "y", "z"), p)) for p in points]
        packets = incarnam_tutorial.walking_guide_packets(
            self.character, self.state, path
        )
        self.assertEqual(
            [
                (struct.unpack(">BiiBq", p[1])[1], struct.unpack(">BiiBq", p[1])[4])
                for p in packets
            ],
            [(22351, 34569), (22351, 34570), (22351, 34571)],
        )
        resume = incarnam_tutorial.resume_walk_guide(self.character, self.state)
        self.assertEqual(struct.unpack(">BiiBq", resume[1])[4], 34571)
        self.assertEqual(
            incarnam_tutorial.walking_guide_packets(
                self.character, {"running": [5136]}, path
            ),
            [],
        )

    def test_ecology_rejects_scripted_intro_proposals_not_ordinary_scopes(self):
        scope = [1361, private_instance_id(217)]
        self.assertTrue(ecology_mobs._scripted_intro_scope(scope))
        self.assertFalse(ecology_mobs._scripted_intro_scope([1361, 0]))
        self.assertFalse(ecology_mobs._scripted_intro_scope([1385, scope[1]]))
        result = ecology_mobs.apply(
            None,
            None,
            None,
            None,
            {"scope": scope, "kind": "wander_bulk", "world_epoch": "now"},
            world_epoch="now",
        )
        self.assertEqual(result, {"status": "stale"})

    def test_repair_only_owner_scripted_group(self):
        from unittest.mock import MagicMock
        from wakfu_server.achievements import incarnam_encounters
        from threading import RLock

        actor = {"id": -42, "ref": 5525, "x": 14, "y": -26, "z": -13}
        stray = {"id": -43, "ref": 5455, "x": 15, "y": -26, "z": -13}
        group = {
            "key": (1361, self.character["instance_id"], 123),
            "members": [actor, stray],
        }
        groups = MagicMock()
        groups.lock = RLock()
        groups.available.return_value = [group]
        db = MagicMock()
        store = MagicMock()
        store.connection.return_value.__enter__.return_value = db
        receipt = {"kind": "incarnam_wodent", "owner": 217, "actor_id": -42, "stage": 1}
        db.execute.return_value.fetchone.side_effect = [
            {"payload": receipt},
            {"group_id": 123},
        ]
        import sys
        from types import SimpleNamespace

        fakes = {
            "wakfu_server.monsters": SimpleNamespace(owned_instance=None),
            "wakfu_server.npc_actor_identity": SimpleNamespace(allocate_block=None),
            "wakfu_server.combat_monster_world": SimpleNamespace(
                spawn_group=lambda *_a, **_kw: b"owned"
            ),
        }
        with patch(
            "wakfu_server.achievements.storage.load_locked",
            return_value={"running": [5135], "completed": []},
        ), patch.dict(sys.modules, fakes):
            self.assertEqual(
                incarnam_encounters.ensure_spawn(store, groups, self.character),
                (12608, b"owned"),
            )
        queries = [call.args[0] for call in db.execute.call_args_list]
        self.assertTrue(
            any(
                "UPDATE combat_groups SET members" in query
                and "status='available'" in query
                for query in queries
            )
        )
        self.assertTrue(
            any(
                "DELETE FROM combat_group_members" in query and "monster_id<>" in query
                for query in queries
            )
        )
        self.assertFalse(
            any(
                "character_achievement" in query
                and ("DELETE" in query or "UPDATE" in query)
                for query in queries
            )
        )


if __name__ == "__main__":
    unittest.main()
