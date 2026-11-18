"""Focused normal-attack autostart from the pinned Huppermage room group."""

import json
from pathlib import Path
import struct
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from wakfu_server import owned_story_auto_start, owned_story_controller

PROFILE = (
    Path(__file__).parents[1]
    / "wakfu_server/maps/owned_story_profiles/huppermage-platform-1030.configuration.json"
)


class Cursor:
    def __init__(self, row=None, rows=None):
        self._row, self._rows = row, list(rows or [])

    def fetchone(self):
        return self._row

    def fetchall(self):
        return self._rows


class OwnedStoryAutoStartTests(unittest.TestCase):
    def setUp(self):
        self.configuration = json.loads(PROFILE.read_text())
        self.selected = owned_story_controller.policy(self.configuration)
        self.character = dict(
            id=81,
            account_id=19,
            map_id=1030,
            instance_id=501,
            x=128,
            y=-15,
            z=0,
        )
        placements = self.configuration["topology"]["rooms"][0]["encounter_scene"][
            "fixed_actor_placements"
        ]
        self.group_members = [
            dict(
                id=-99001 - index,
                ref=placement["reference"],
                x=placement["cell"][0],
                y=placement["cell"][1],
                z=placement["cell"][2],
                map_id=1030,
                instance_id=501,
            )
            for index, placement in enumerate(placements)
        ]
        self.group = dict(
            group_id=701, members=[dict(row) for row in self.group_members]
        )
        self.durable_group = dict(
            group_id=701,
            asset_map_id=1030,
            members=[dict(row) for row in self.group_members],
            status="available",
        )
        self.members = [dict(character_id=81)]
        self.story_receipt = dict(
            schema=owned_story_controller.SCHEMA,
            profile_sha256=owned_story_controller._digest(self.selected),
            owner=81,
            instance_id=501,
            step="platform-ready",
        )
        self.db = self.Database(self)
        self.store = self.Store(self.db, self.character)
        self.state = SimpleNamespace(
            loaded=True,
            character=dict(self.character),
            fight=None,
            combat_session=None,
            spectator_session=None,
            pending_guardian_attack=None,
            connection=SimpleNamespace(owned_story_auto_frontier=None),
            account_id=19,
            generation="generation-1",
        )
        self.session = SimpleNamespace(
            state=self.state, runtime=SimpleNamespace(STORE=self.store)
        )

    class Database:
        def __init__(self, case):
            self.case = case
            self.calls = []

        def execute(self, query, params=None):
            self.calls.append((query, params))
            if "SELECT i.context_route_key" in query:
                return Cursor(
                    dict(
                        context_route_key=self.case.configuration["route"]["key"],
                        context_policy_version=self.case.configuration["version"],
                        start_map_id=self.case.configuration["topology"][
                            "asset_map_id"
                        ],
                    )
                )
            if "SELECT character_id FROM dungeon_instance_members" in query:
                return Cursor(rows=self.case.members)
            if "SELECT map_id,instance_id,x,y,z FROM characters" in query:
                return Cursor(
                    {
                        key: self.case.character[key]
                        for key in ("map_id", "instance_id", "x", "y", "z")
                    }
                )
            if "SELECT event_key,payload FROM character_achievement_events" in query:
                receipt = self.case.story_receipt
                return Cursor(
                    rows=[
                        dict(
                            event_key="owned-story:huppermage-platform-1030:501:platform-ready",
                            payload=receipt,
                        )
                    ]
                )
            if "SELECT r.group_id,r.asset_map_id,g.members,g.status" in query:
                return Cursor(dict(self.case.durable_group))
            raise AssertionError(f"Unexpected SQL in focused autostart test: {query}")

    class Store:
        def __init__(self, db, character):
            self.db, self.character_row = db, character

        def connection(self):
            return self

        def __enter__(self):
            return self.db

        def __exit__(self, *_args):
            return False

        def character(self, account_id, character_id, _db):
            if (account_id, character_id) != (19, 81):
                return None
            return dict(self.character_row)

    def call_queue(self):
        with patch(
            "wakfu_server.dungeon_runtime_config.pinned_configuration",
            return_value=self.configuration,
        ):
            return owned_story_auto_start.queue(
                self.session, self.group, configuration=self.configuration
            )

    def test_loaded_sole_owner_queues_only_the_durable_native_group(self):
        # Runtime group providers return an ordered tuple while PostgreSQL's
        # JSON group membership is decoded as a list.
        self.group["members"] = tuple(dict(row) for row in self.group_members)
        self.assertTrue(self.call_queue())
        self.assertEqual(
            self.state.pending_guardian_attack,
            struct.pack(">qiihB", -99001, 124, -15, 0, 0),
        )
        self.assertEqual(len(self.db.calls), 4)
        self.assertTrue(
            owned_story_auto_start.queue(
                self.session, self.group, configuration=self.configuration
            )
            is False
        )
        self.assertEqual(len(self.db.calls), 4)  # Duplicate pending queue is inert.

        self.state.pending_guardian_attack = None
        changed = [dict(row) for row in self.group_members]
        changed[1]["id"] -= 1
        self.group["members"] = tuple(changed)
        with self.assertRaisesRegex(
            ValueError, "differs from its durable native group"
        ):
            self.call_queue()
        self.assertIsNone(self.state.pending_guardian_attack)
        self.assertEqual(len(self.db.calls), 8)

    def test_wild_estate_room_two_waits_for_actual_pose_then_queues_native_group(self):
        path = Path(__file__).parents[1] / (
            "wakfu_server/maps/owned_story_profiles/"
            "wild-estate-excavation-713.configuration.json"
        )
        self.configuration = json.loads(path.read_text())
        self.selected = owned_story_controller.policy(self.configuration)
        self.character.update(map_id=713, x=3, y=0, z=0)
        self.state.character.update(map_id=713, x=3, y=0, z=0)
        self.group_members = [
            dict(
                id=-71302 - index,
                ref=2765,
                x=12,
                y=8 + index,
                z=0,
                map_id=713,
                instance_id=501,
            )
            for index in range(2)
        ]
        self.group = dict(
            group_id=702, members=[dict(row) for row in self.group_members]
        )
        self.durable_group = dict(
            group_id=702,
            asset_map_id=713,
            members=[dict(row) for row in self.group_members],
            status="available",
            room_order=2,
        )
        self.story_receipt = dict(
            schema=owned_story_controller.SCHEMA,
            profile_sha256=owned_story_controller._digest(self.selected),
            owner=81,
            instance_id=501,
            step="excavation-first-victory",
        )

        before_room = dict(self.character)
        before_orders = owned_story_auto_start.ready_room_orders(
            self.configuration, before_room
        )
        before_frontier = (501, ("excavation-first-victory",), before_orders)
        self.assertEqual(before_orders, (1,))
        self.assertFalse(self.call_queue())
        self.assertIsNone(self.state.pending_guardian_attack)

        self.character.update(x=12, y=6, z=0)
        self.state.character.update(x=12, y=6, z=0)
        actual_orders = owned_story_auto_start.ready_room_orders(
            self.configuration, self.character
        )
        after_frontier = (501, ("excavation-first-victory",), actual_orders)
        self.assertEqual(actual_orders, (2,))
        self.assertNotEqual(before_frontier, after_frontier)
        self.assertEqual(
            owned_story_auto_start.ready_room_orders(
                self.configuration, dict(self.character, map_id=714)
            ),
            (),
        )
        self.assertTrue(self.call_queue())
        self.assertEqual(
            self.state.pending_guardian_attack,
            struct.pack(">qiihB", -71302, 12, 8, 0, 0),
        )

    def test_temple_corridor_queues_boulder_only_after_readiness_at_owner_pose(self):
        path = Path(__file__).parents[1] / (
            "wakfu_server/maps/owned_story_profiles/"
            "wild-temple-718.configuration.json"
        )
        self.configuration = json.loads(path.read_text())
        self.assertEqual(self.configuration["version"], 2)
        self.selected = owned_story_controller.policy(self.configuration)
        room = next(
            row for row in self.configuration["topology"]["rooms"] if row["order"] == 8
        )
        self.assertEqual(
            owned_story_auto_start.requirements(self.selected, 8)["requires"],
            ["corridor-started"],
        )
        (placement,) = room["encounter_scene"]["fixed_actor_placements"]
        self.assertEqual(placement["reference"], 2806)
        self.assertEqual(placement["cell"], [8, 60, -36])
        self.character.update(map_id=718, x=12, y=60, z=-36)
        self.state.character.update(self.character)
        self.group_members = [
            dict(
                id=-71808,
                ref=placement["reference"],
                map_id=718,
                instance_id=501,
                **dict(zip(("x", "y", "z"), placement["cell"])),
            )
        ]
        self.group = dict(group_id=708, members=tuple(self.group_members))
        self.durable_group = dict(
            group_id=708,
            asset_map_id=718,
            room_order=8,
            members=self.group_members,
            status="available",
        )
        self.story_receipt = dict(
            schema=owned_story_controller.SCHEMA,
            profile_sha256=owned_story_controller._digest(self.selected),
            owner=81,
            instance_id=501,
            step="artifact-taken",
        )
        original_execute = self.db.execute

        def execute(query, params=None):
            if "SELECT event_key,payload FROM character_achievement_events" in query:
                return Cursor(
                    rows=[
                        dict(
                            event_key=(
                                "owned-story:wild-temple-718:501:"
                                + self.story_receipt["step"]
                            ),
                            payload=self.story_receipt,
                        )
                    ]
                )
            return original_execute(query, params)

        with patch.object(self.db, "execute", side_effect=execute):
            # The artifact alone cannot start the chase before physical20702.
            self.assertFalse(self.call_queue())
            self.assertIsNone(self.state.pending_guardian_attack)
            self.story_receipt["step"] = "corridor-started"
            self.character.update(x=12, y=58)
            self.state.character.update(self.character)
            self.assertFalse(self.call_queue())
            self.assertIsNone(self.state.pending_guardian_attack)
            self.character.update(x=12, y=60)
            self.state.character.update(self.character)
            self.assertTrue(self.call_queue())

        self.assertEqual(
            self.state.pending_guardian_attack,
            struct.pack(">qiihB", -71808, 8, 60, -36, 0),
        )
        ticket = self.state.owned_story_ambush_admission
        self.assertEqual(ticket["room_order"], 8)
        self.assertEqual(ticket["ready_steps"], ("corridor-started",))
        self.assertEqual(
            ticket["pose"],
            dict(
                map_id=718,
                instance_id=501,
                x=12,
                y=60,
                z=-36,
            ),
        )
        self.assertEqual(self.state.character["x"] - placement["cell"][0], 4)

    def test_loading_multiowner_fighting_or_stale_group_never_queues(self):
        self.state.loaded = False
        self.assertFalse(self.call_queue())
        self.assertEqual(self.db.calls, [])
        self.state.loaded = True
        self.members.append(dict(character_id=82))
        with self.assertRaisesRegex(ValueError, "one original owner"):
            self.call_queue()
        self.members = [dict(character_id=81)]
        self.state.fight = object()
        self.assertFalse(self.call_queue())
        self.state.fight = None
        self.durable_group["asset_map_id"] = 1017
        with self.assertRaisesRegex(ValueError, "durable native group"):
            self.call_queue()
        self.assertIsNone(self.state.pending_guardian_attack)


if __name__ == "__main__":
    unittest.main()
