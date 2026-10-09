"""Native door requests cannot invent room order or bypass source authority."""

import struct
import unittest
import uuid
from types import SimpleNamespace

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import dungeon_instances
from wakfu_server.maps import dungeon_doors
from wakfu_server.maps.dungeon_progression import (
    bind_encounter,
    initialize_run,
    settle_encounter,
)
from wakfu_server.maps.dungeon_doors import resolve


class DungeonDoorResolutionTests(unittest.TestCase):
    def resolve(self, **overrides):
        arguments = dict(
            source_allowed=lambda character, source: True,
            room_for_position=lambda map_id, x, y, z: 1 if x == 0 else 2,
            criterion_allowed=lambda criterion: True,
        )
        arguments.update(overrides)
        return resolve(
            dict(map_id=1086, instance_id=144115188075855873),
            struct.pack(">qiBi", 26845, 2506, 0, 2),
            **arguments,
        )

    def test_native_forward_route_preserves_topology_authority(self):
        first, second, destination = self.resolve()
        self.assertEqual((first, second), (1, 2))
        self.assertEqual(
            (destination["map_id"], destination["x"], destination["y"]),
            (1086, 152, -10),
        )

    def test_denied_source_or_criterion_fails_closed(self):
        for overrides in (
            dict(source_allowed=lambda character, source: False),
            dict(criterion_allowed=lambda criterion: False),
        ):
            with self.assertRaises(ValueError):
                self.resolve(**overrides)

    def test_missing_or_nonadjacent_room_mapping_fails_closed(self):
        for mapper in (
            lambda *position: None,
            lambda *position: 1,
            lambda map_id, x, y, z: 1 if x == 0 else 3,
        ):
            with self.assertRaises(ValueError):
                self.resolve(room_for_position=mapper)


class DungeonDoorProgressionTests(PostgresCase):
    """Test door authorization and party movement in a disposable schema."""

    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    enter = Fixture.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)
        self.members, self.party_id = self.party(2)
        self.instance = self.enter(self.members[0])
        self.instance_id = self.instance["instance_id"]
        monster = SimpleNamespace(
            ref_id=1,
            count=1,
            native_min_level=1,
            native_max_level=5,
            role="monster",
        )
        plan = SimpleNamespace(
            roster_ready=True,
            document_sha256="b" * 64,
            rooms=tuple(
                SimpleNamespace(order=order, monsters=(monster,)) for order in (1, 2)
            ),
        )
        with self.store.connection() as db:
            initialize_run(db, self.instance_id, self.party_id, plan)

    def topology_room(self, map_id, x, y, z):
        if map_id != 1086 or z != 0:
            return None
        native_door_rooms = {
            (0, -27): 1,
            (152, -10): 2,
            (152, -9): 2,
            (0, -26): 1,
        }
        return native_door_rooms.get((int(x), int(y)))

    def forward_request(self):
        return struct.pack(">qiBi", 26845, 2506, 0, 2)

    def reverse_request(self):
        return struct.pack(">qiBi", 26849, 2509, 0, 2)

    def source_check(self, character, source):
        # The synthetic topology grants approach only at the tested door side.
        point = (round(character["x"]), round(character["y"]))
        source_point = (round(source["x"]), round(source["y"]))
        return point in {(4, -12), (152, -10)} and source_point in {(0, -27), (152, -9)}

    def authorize_room_one(self):
        fight_id = self.make_fight(self.members[0])
        with self.store.connection() as db:
            bind_encounter(
                db,
                self.instance_id,
                self.party_id,
                self.members[0]["character"]["id"],
                fight_id,
                player_team=0,
            )
            db.execute(
                "UPDATE combat_fights SET status='finished' WHERE id=%s", (fight_id,)
            )
            result = settle_encounter(
                db, SimpleNamespace(id=fight_id, phase="finished", winner=0)
            )
        self.assertTrue(result["victory"])

    def make_fight(self, member):
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants(fight_id,character_id,account_id,team) "
                "VALUES(%s,%s,%s,0)",
                (fight_id, member["character"]["id"], member["account"]),
            )
        return fight_id

    def run_state(self):
        with self.store.connection() as db:
            return db.execute(
                "SELECT revision FROM dungeon_instances WHERE instance_id=%s",
                (self.instance_id,),
            ).fetchone()["revision"]

    def advance(
        self, body=None, *, in_fight=lambda _character_id: False, source_allowed=None
    ):
        return dungeon_doors.advance(
            self.store,
            self.members[0]["account"],
            self.members[0]["generation"],
            self.members[0]["character"]["id"],
            self.forward_request() if body is None else body,
            source_allowed=source_allowed or self.source_check,
            room_for_position=self.topology_room,
            in_fight=in_fight,
        )

    def test_next_room_is_rejected_before_committed_victory(self):
        with self.assertRaisesRegex(ValueError, "victory authorization"):
            self.advance()
        self.assertEqual(1, self.run_state())
        for member in self.members:
            character = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.assertEqual(
                (self.instance_id, 4, -12),
                (character["instance_id"], character["x"], character["y"]),
            )

    def test_victory_advances_all_members_and_preserves_private_instance(self):
        self.authorize_room_one()
        result = self.advance()
        self.assertEqual(2, len(result["members"]))
        self.assertEqual(self.instance_id, result["instance_id"])
        for member in self.members:
            character = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.assertEqual(
                (1086, self.instance_id, 152, -10),
                (
                    character["map_id"],
                    character["instance_id"],
                    character["x"],
                    character["y"],
                ),
            )
            events = dungeon_instances.pending_transitions(
                self.store,
                member["account"],
                member["generation"],
                member["character"]["id"],
            )
            door_events = [
                event for event in events if event["transition_kind"] == "door"
            ]
            self.assertEqual(1, len(door_events))
            self.assertEqual(
                self.instance_id, door_events[0]["destination_instance_id"]
            )
        with self.store.connection() as db:
            self.assertEqual(
                2,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox "
                    "WHERE instance_id=%s AND transition_kind='door' AND status='pending'",
                    (self.instance_id,),
                ).fetchone()["n"],
            )

    def test_combat_rejects_door_without_moving_or_creating_events(self):
        self.authorize_room_one()
        revision = self.run_state()
        with self.assertRaisesRegex(ValueError, "outside combat"):
            self.advance(in_fight=lambda _character_id: True)
        self.assertEqual(revision, self.run_state())
        with self.store.connection() as db:
            self.assertEqual(
                0,
                db.execute(
                    "SELECT count(*) AS n FROM dungeon_transition_outbox "
                    "WHERE instance_id=%s AND transition_kind='door'",
                    (self.instance_id,),
                ).fetchone()["n"],
            )

    def test_reverse_route_and_duplicate_stale_request_fail_source_check(self):
        self.authorize_room_one()
        self.advance()
        # The reverse door is usable from room two and returns the whole party.
        result = self.advance(self.reverse_request())
        self.assertEqual(self.instance_id, result["instance_id"])
        for member in self.members:
            character = self.store.character(
                member["account"], member["character"]["id"]
            )
            self.assertEqual(
                (self.instance_id, 0, -26),
                (character["instance_id"], character["x"], character["y"]),
            )
        # Retrying the previous forward request from room one fails the approach check.
        with self.assertRaisesRegex(ValueError, "source is not authorized"):
            self.advance()
