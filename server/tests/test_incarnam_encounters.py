import struct
import unittest
from unittest.mock import patch

from wakfu_server.achievements import incarnam_encounters as module
from wakfu_server.intro_cinematic import private_instance_id


class FakeDB:
    def __init__(self, payload):
        self.payload = payload

    def execute(self, *_args):
        return self

    def fetchone(self):
        return {"payload": self.payload} if self.payload else None


class IncarnamEncounterTests(unittest.TestCase):
    def test_normal_tutorial_fight_exit_keeps_loaded_lua_world(self):
        owner = {"id": 7, "map_id": 1361, "instance_id": private_instance_id(7)}
        packets = [(13256, b""), (13974, b"world"), (12318, b"region")]
        self.assertEqual(
            module.return_bootstrap(owner, packets, abandoned=False),
            ((12318, b"region"),),
        )
        self.assertEqual(
            module.return_bootstrap(owner, packets, abandoned=True), tuple(packets)
        )
        self.assertEqual(
            module.return_bootstrap(
                {**owner, "instance_id": 0}, packets, abandoned=False
            ),
            tuple(packets),
        )

    def setUp(self):
        self.character = {
            "id": 7,
            "map_id": 1361,
            "instance_id": private_instance_id(7),
        }
        self.member = {"id": -10, "ref": 5525, "x": 12, "y": -18, "z": -16}
        self.group = {
            "key": (1361, self.character["instance_id"], 9),
            "members": [self.member],
        }
        self.payload = {
            "kind": "incarnam_wodent",
            "owner": 7,
            "actor_id": -10,
            "stage": 1,
        }
        self.first = {"running": [5135], "completed": []}

    def test_native_attack_is_bound_to_owner_actor_action_and_stage(self):
        with patch.object(module, "scene_owner", return_value=True), patch(
            "wakfu_server.achievements.storage.load_locked", return_value=self.first
        ):
            result = module.prepare(
                FakeDB(self.payload),
                self.character,
                struct.pack(">qq", -10, 1254),
                self.group,
            )
            self.assertEqual(result["incarnam_stage"], 1)
            self.assertEqual(result["position"], (12, -18, -16))
            self.assertIsNone(
                module.prepare(
                    FakeDB(self.payload),
                    self.character,
                    struct.pack(">qq", -10, 99),
                    self.group,
                )
            )
            with self.assertRaises(ValueError):
                module.prepare(
                    FakeDB({**self.payload, "owner": 8}),
                    self.character,
                    struct.pack(">qq", -10, 1254),
                    self.group,
                )

    def test_second_wodent_visible_before_quest_but_not_attackable(self):
        state = {"running": [5136], "completed": [5135]}
        self.assertEqual(module.stage(state), 2)
        with patch("wakfu_server.achievements.storage.load_locked", return_value=state):
            with self.assertRaises(ValueError):
                module.prepare(
                    FakeDB({**self.payload, "stage": 2}),
                    self.character,
                    struct.pack(">qq", -10, 1254),
                    self.group,
                )
            state["running"] = [5139]
            self.assertEqual(
                module.prepare(
                    FakeDB({**self.payload, "stage": 2}),
                    self.character,
                    struct.pack(">qq", -10, 1254),
                    self.group,
                )["incarnam_stage"],
                2,
            )

    def test_private_instance_required(self):
        self.assertTrue(module.scene_owner(self.character))
        self.assertFalse(module.scene_owner({**self.character, "instance_id": 0}))
        self.assertFalse(module.scene_owner({**self.character, "id": 8}))

    def test_captured_combat_guide_events_follow_accepted_actions(self):
        from types import SimpleNamespace
        import struct

        fight = SimpleNamespace(
            id=35, phase="active", actors={7: SimpleNamespace(ap=2)}
        )
        for step, move_event, cast_step in ((1, 22514, 10), (2, 22528, 50)):
            guides = module.CombatGuides(35, 7, step)
            self.assertEqual(guides.observe(fight, 8, "move"), [])
            packet = guides.observe(fight, 7, "move")[0]
            self.assertEqual(struct.unpack(">BiiB", packet[1])[1:3], (move_event, 2500))
            self.assertEqual(guides.observe(fight, 7, "move"), [])
            cast = guides.observe(fight, 7, "cast")[0]
            self.assertEqual(
                struct.unpack(">BiiBq", cast[1])[1:], (22529, 2500, 1, cast_step)
            )
            turn = guides.observe(fight, 7, "end_turn")
            self.assertEqual(bool(turn), step == 1)
            self.assertEqual(guides.observe(fight, 7, "end_turn"), [])

    def test_guides_recover_only_from_owned_encounter_receipt(self):
        from types import SimpleNamespace

        fight = SimpleNamespace(
            id=35, phase="active", actors={7: object(), -10: object()}
        )
        db = FakeDB(self.payload)
        db.fetchall = lambda: [{"payload": self.payload}]
        self.assertEqual(module.recover_guides(db, self.character, fight).stage, 1)
        db.fetchall = lambda: [{"payload": {**self.payload, "owner": 8}}]
        self.assertIsNone(module.recover_guides(db, self.character, fight))
        fight.phase = "finished"
        self.assertIsNone(module.recover_guides(db, self.character, fight))

    def test_victory_delivers_progress_to_account_not_character(self):
        from types import SimpleNamespace
        from unittest.mock import MagicMock

        player, enemy = SimpleNamespace(team=0), SimpleNamespace(team=1)
        fight = SimpleNamespace(
            id=478, phase="finished", winner=0, actors={7: player, -10: enemy}
        )
        db = MagicMock()
        db.execute.return_value.fetchone.side_effect = [
            {"payload": self.payload},
            {"status": "finished", "fight_kind": "pve", "team": 0},
        ]
        store = MagicMock()
        store.character.return_value = self.character
        member = {"character_id": 7, "account_id": 153, "session_generation": "valid"}
        expected = [(13832, b"objective")]
        with patch(
            "wakfu_server.achievements.incarnam_tutorial.settle", return_value=expected
        ):
            delivered = module.settle(db, store, fight, [member], [self.member])
        self.assertEqual(delivered, {153: expected})
        self.assertTrue(
            all(
                isinstance(p, tuple) and isinstance(p[1], bytes) for p in delivered[153]
            )
        )

    def test_tutorial_arena_preserves_connected_floor_and_rejects_others(self):
        for stage, y, z in ((1, -18, -16), (2, -54, -10)):
            character = {**self.character, "x": 13, "y": y, "z": z}
            monster = {**self.member, "x": 12, "y": y, "z": z}
            cells = [(12, y, z), (13, y, z), (14, y, z), (12, y, z + 3)]
            geometry = {
                "cells": cells,
                "edges": [
                    (cells[0], cells[1]),
                    (cells[1], cells[0]),
                    (cells[1], cells[2]),
                    (cells[2], cells[1]),
                ],
            }
            policy = module.arena_policy(
                FakeDB({**self.payload, "stage": stage}), character, [monster], geometry
            )
            self.assertEqual(policy["allowed_cells"], set(cells[:3]))
            self.assertFalse(policy["relocate_monsters"])
            self.assertFalse(policy["ordinary_npc_placement"])
            with self.assertRaises(ValueError):
                module.arena_policy(
                    FakeDB({**self.payload, "stage": stage}),
                    {**character, "z": z + 3},
                    [monster],
                    geometry,
                )
            self.assertIsNone(
                module.arena_policy(
                    FakeDB({**self.payload, "owner": 8, "stage": stage}),
                    character,
                    [monster],
                    geometry,
                )
            )


if __name__ == "__main__":
    unittest.main()
