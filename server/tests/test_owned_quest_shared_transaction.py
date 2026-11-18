"""PostgreSQL proof that paired dungeon leave/entry share one transaction."""

import struct

from postgres_case import PostgresCase
import test_dungeon_instances as dungeon_fixture
from wakfu_server.maps import dungeon_exit, dungeon_transport


class OwnedQuestSharedTransactionTests(PostgresCase):
    # Reuse only the fixture methods; inheriting the fixture suite would run all
    # of its dungeon tests again.
    player = dungeon_fixture.DungeonInstanceTests.player
    install_context_policy = dungeon_fixture.DungeonInstanceTests.install_context_policy
    enter = dungeon_fixture.DungeonInstanceTests.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)

    def _leave(self, player, db=None):
        return dungeon_exit._leave(
            self.store,
            player["account"],
            player["generation"],
            player["character"]["id"],
            in_fight=lambda _character_id: False,
            destination_for=lambda *_: dict(map_id=527, x=-245, y=-90, z=2),
            _db=db,
        )

    def _enter(self, player, db=None, initializer=None):
        return dungeon_transport._enter(
            self.store,
            player["account"],
            player["generation"],
            player["character"]["id"],
            527,
            struct.pack(">qiBi", 26842, 2504, 0, 2),
            criterion_allowed=lambda *_: True,
            source_allowed=lambda *_: True,
            initialize_instance=initializer,
            _db=db,
        )

    def _snapshot(self, character_id):
        with self.store.connection() as db:
            character = db.execute(
                "SELECT id,map_id,instance_id,x,y,z FROM characters WHERE id=%s",
                (character_id,),
            ).fetchone()
            memberships = db.execute(
                "SELECT instance_id,character_id,status,session_generation "
                "FROM dungeon_instance_members WHERE character_id=%s ORDER BY instance_id",
                (character_id,),
            ).fetchall()
            parties = db.execute(
                "SELECT p.id,p.leader_id,p.dungeon_solo,m.character_id "
                "FROM player_parties p LEFT JOIN player_party_members m ON m.party_id=p.id "
                "WHERE p.id IN (SELECT party_id FROM player_party_members WHERE character_id=%s) "
                "OR p.leader_id=%s ORDER BY p.id,m.character_id",
                (character_id, character_id),
            ).fetchall()
            outbox = db.execute(
                "SELECT instance_id,party_id,transition_revision,character_id,"
                "session_generation,source_instance_id,destination_map_id,"
                "destination_instance_id,destination_x,destination_y,destination_z,"
                "transition_kind,status FROM dungeon_transition_outbox "
                "WHERE character_id=%s ORDER BY event_id",
                (character_id,),
            ).fetchall()
            instances = db.execute(
                "SELECT i.instance_id,i.party_id,i.status,i.revision "
                "FROM dungeon_instances i JOIN dungeon_instance_members m USING(instance_id) "
                "WHERE m.character_id=%s ORDER BY i.instance_id",
                (character_id,),
            ).fetchall()
        return character, memberships, parties, outbox, instances

    def test_shared_database_transaction_rolls_back_then_commits_and_cleans_selection(
        self,
    ):
        player = self.player("shared-transaction")
        original = self.enter(player)
        character_id = player["character"]["id"]

        before_failure = self._snapshot(character_id)

        def fail_initializer(_db, _session):
            raise RuntimeError("forced target initialization failure")

        with self.assertRaisesRegex(
            RuntimeError, "forced target initialization failure"
        ):
            with self.store.connection() as db:
                self._leave(player, db)
                self._enter(player, db, fail_initializer)

        self.assertEqual(self._snapshot(character_id), before_failure)

        with self.store.connection() as db:
            self._leave(player, db)
            entered = self._enter(player, db)
        self.assertNotEqual(entered["instance_id"], original["instance_id"])
        state = self._snapshot(character_id)
        self.assertEqual(state[0]["instance_id"], entered["instance_id"])
        self.assertEqual(len(state[2]), 1)
        self.assertTrue(state[2][0]["dungeon_solo"])
        pending_entry = [row for row in state[3] if row["status"] == "pending"]
        self.assertTrue(
            any(row["transition_kind"] == "enter" for row in pending_entry), state[3]
        )
        pending_target = next(
            row for row in pending_entry if row["transition_kind"] == "enter"
        )
        self.assertEqual(
            pending_target["destination_instance_id"], entered["instance_id"]
        )

        # The ordinary public exit path must remain safe across character
        # selection changes after the paired transfer has committed.
        exited = dungeon_exit.leave(
            self.store,
            player["account"],
            player["generation"],
            character_id,
            struct.pack(">qiBi", 26843, 2505, 0, 2),
            source_allowed=lambda *_: True,
            in_fight=lambda _character_id: False,
        )
        self.assertEqual(exited["instance_id"], 0)
        self.assertEqual(self._snapshot(character_id)[2], [])
        with self.store.connection() as db:
            pending = db.execute(
                "SELECT transition_kind,destination_map_id,destination_instance_id,"
                "destination_x,destination_y,destination_z "
                "FROM dungeon_transition_outbox WHERE character_id=%s AND status='pending'",
                (character_id,),
            ).fetchall()
        self.assertEqual(
            pending,
            [
                {
                    "transition_kind": "exit",
                    "destination_map_id": 527,
                    "destination_instance_id": 0,
                    "destination_x": exited["x"],
                    "destination_y": exited["y"],
                    "destination_z": exited["z"],
                }
            ],
        )

        other = self.store.create_character(player["account"], "Altcharacter")
        self.store.select_character(
            player["account"], player["generation"], other["id"]
        )
        selected_old = self.store.select_character(
            player["account"], player["generation"], character_id
        )
        self.assertEqual(selected_old["instance_id"], 0)
        self.assertEqual(
            tuple(selected_old[key] for key in ("map_id", "x", "y", "z")),
            tuple(exited[key] for key in ("map_id", "x", "y", "z")),
        )
