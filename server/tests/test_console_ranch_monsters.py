"""Privileged monster creation uses a trusted private host scope."""
from unittest.mock import patch

from postgres_case import PostgresCase
from wakfu_server.combat_geometry import prepare_geometry
from wakfu_server.combat_groups import Groups
from wakfu_server.command_permissions import set_admin
from wakfu_server.haven_bag import HavenBagSession
from wakfu_server.haven_ranch import POSITION, RanchSession, destination
from wakfu_server.test_console import execute


class RanchMonsterConsoleTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.host = self.store.register("host", "password")["id"]
        self.owner = self.store.create_character(self.host, "Host")
        self.generation = self.store.begin_session(self.host)
        self.store.select_character(self.host, self.generation, self.owner["id"])
        set_admin(self.store, self.host, True, operator="test", reason="fixture")
        self.groups = Groups()
        self.geometry = prepare_geometry(
            dict(
                map_id=1440,
                cells=[(10, 10, 0), (11, 10, 0), (12, 10, 0)],
                edges=[((10, 10, 0), (11, 10, 0)), ((11, 10, 0), (12, 10, 0))],
            )
        )

    def scene(self, character, generation, *, owner=None):
        bag = HavenBagSession(character, owner=owner)
        ranch = RanchSession(
            bag, bag.inside, destination(35), lease=generation, now_ms=1
        )
        return ranch, ranch.move(ranch.inside, dict(x=10, y=10, z=0))

    def spawn(self, account, generation, character, scene, command="!monster 5525 1 1"):
        with patch(
            "wakfu_server.test_console.published_geometry", return_value=self.geometry
        ):
            return execute(
                self.store,
                self.groups,
                account,
                generation,
                character,
                command,
                private_scene=scene,
            )

    def test_owner_spawn_is_private_and_sql_exterior_never_changes(self):
        ranch, live = self.scene(self.owner, self.generation)
        result = self.spawn(self.host, self.generation, live, ranch)
        self.assertEqual(result["world_packets"][0][0], 12608)
        self.assertEqual(result["group_key"][:2], (1440, self.owner["id"]))
        self.assertEqual(result["members"][0]["instance_id"], self.owner["id"])
        self.assertEqual(len(self.groups.available(1440, self.owner["id"])), 1)
        self.assertEqual(self.groups.available(1440, self.owner["id"] + 1), [])
        saved = self.store.character(self.host, self.owner["id"])
        self.assertEqual(
            {k: saved[k] for k in POSITION}, {k: self.owner[k] for k in POSITION}
        )
        with self.assertRaises(ValueError):
            self.spawn(self.host, self.generation, {**live, "instance_id": 999}, ranch)
        with self.assertRaises(ValueError):
            self.spawn(self.host, self.generation, live, object())

    def test_guest_requires_command_privilege_and_spawns_in_host_not_own_scope(self):
        guest_account = self.store.register("guest", "password")["id"]
        guest = self.store.create_character(guest_account, "Guest")
        generation = self.store.begin_session(guest_account)
        self.store.select_character(guest_account, generation, guest["id"])
        ranch, live = self.scene(guest, generation, owner=self.owner)
        with self.assertRaises(PermissionError):
            self.spawn(guest_account, generation, live, ranch)
        set_admin(self.store, guest_account, True, operator="test", reason="fixture")
        result = self.spawn(guest_account, generation, live, ranch, "!mob 5525 1 1")
        self.assertEqual(result["group_key"][:2], (1440, self.owner["id"]))
        self.assertEqual(self.groups.available(1440, guest["id"]), [])
        self.assertTrue(result["character"]["haven_bag_visitor"])
        self.store.begin_session(guest_account)
        with self.assertRaises(ValueError):
            self.spawn(guest_account, generation, live, ranch)
