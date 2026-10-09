"""Live party dissolution retains foreign-key-owned dungeon history."""
import test_dungeon_instances as fixture
from postgres_case import PostgresCase
from wakfu_server import player_parties


class RetainedDungeonPartyTests(PostgresCase):
    install_context_policy = fixture.DungeonInstanceTests.install_context_policy
    player = fixture.DungeonInstanceTests.player
    party = fixture.DungeonInstanceTests.party
    enter = fixture.DungeonInstanceTests.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)

    def prepare(self, status):
        members, party_id = self.party(2)
        run = self.enter(members[0])
        with self.store.connection() as db:
            if status != "active":
                db.execute(
                    "UPDATE dungeon_instances SET status=%s,ended_at=%s WHERE instance_id=%s",
                    (status, self.store.now(), run["instance_id"]),
                )
            before = db.execute(
                "SELECT * FROM dungeon_instance_members WHERE instance_id=%s ORDER BY character_id",
                (run["instance_id"],),
            ).fetchall()
            db.execute(
                "DELETE FROM sessions WHERE account_id=%s", (members[1]["account"],)
            )
        return members, party_id, run, before

    def assert_retained(self, party_id, run, status, before):
        with self.store.connection() as db:
            party = db.execute(
                "SELECT * FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()
            self.assertIsNone(party["leader_id"])
            self.assertGreater(party["revision"], 1)
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (party_id,),
                ).fetchone()["n"],
                0,
            )
            history = db.execute(
                "SELECT party_id,status FROM dungeon_instances WHERE instance_id=%s",
                (run["instance_id"],),
            ).fetchone()
            self.assertEqual(history, {"party_id": party_id, "status": status})
            after = db.execute(
                "SELECT * FROM dungeon_instance_members WHERE instance_id=%s ORDER BY character_id",
                (run["instance_id"],),
            ).fetchall()
            self.assertEqual(after, before)

    def test_self_leave_with_offline_survivor_retains_active_and_completed_history(
        self,
    ):
        for status in ("active", "completed", "closed"):
            with self.subTest(status=status):
                members, party_id, run, before = self.prepare(status)
                actor = members[0]
                change = player_parties.change_member(
                    self.store,
                    actor["account"],
                    actor["generation"],
                    actor["character"]["id"],
                    party_id,
                    actor["character"]["id"],
                )
                self.assertEqual(
                    set(change["removed"]),
                    {member["character"]["id"] for member in members},
                )
                self.assertIsNone(change["leader_id"])
                self.assert_retained(party_id, run, status, before)
                self.assertIsNone(
                    player_parties.snapshot(
                        self.store,
                        actor["account"],
                        actor["generation"],
                        actor["character"]["id"],
                    )
                )

    def test_character_deletion_retains_dungeon_history_and_offline_survivor(self):
        members, party_id, run, before = self.prepare("completed")
        actor = members[0]
        with self.store.connection() as db:
            db.execute(
                "UPDATE sessions SET character_id=NULL WHERE account_id=%s",
                (actor["account"],),
            )
        change = self.store.delete_character(
            actor["account"], actor["generation"], actor["character"]["id"]
        )
        self.assertEqual(
            set(change["party_change"]["removed"]),
            {member["character"]["id"] for member in members},
        )
        self.assert_retained(party_id, run, "completed", before)
