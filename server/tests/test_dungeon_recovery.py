"""Selected lease recovery preserves private location and fences old delivery."""

from postgres_case import PostgresCase
from test_dungeon_instances import DungeonInstanceTests as Fixture
from wakfu_server import dungeon_instances
from wakfu_server.maps.dungeon_recovery import resume_member


class DungeonRecoveryTests(PostgresCase):
    install_context_policy = Fixture.install_context_policy
    player = Fixture.player
    party = Fixture.party
    enter = Fixture.enter

    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.install_context_policy(1)

    def test_new_selected_generation_rebinds_only_owned_member(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        actor = members[0]
        before = self.store.character(actor["account"], actor["character"]["id"])
        generation = self.store.begin_session(actor["account"], ttl=10000)
        self.store.select_character(
            actor["account"], generation, actor["character"]["id"]
        )
        result = resume_member(
            self.store,
            actor["account"],
            generation,
            actor["character"]["id"],
            run["instance_id"],
        )
        self.assertTrue(result["rebound"])
        self.assertIsNotNone(
            dungeon_instances.authorize_member(
                self.store,
                actor["account"],
                generation,
                actor["character"]["id"],
                run["instance_id"],
            )
        )
        after = self.store.character(actor["account"], actor["character"]["id"])
        self.assertEqual(
            tuple(before[key] for key in ("map_id", "instance_id", "x", "y", "z")),
            tuple(after[key] for key in ("map_id", "instance_id", "x", "y", "z")),
        )
        with self.store.connection() as db:
            rows = db.execute(
                "SELECT character_id,session_generation FROM dungeon_instance_members ORDER BY character_id"
            ).fetchall()
            old = db.execute(
                "SELECT status FROM dungeon_transition_outbox WHERE character_id=%s",
                (actor["character"]["id"],),
            ).fetchone()
        self.assertEqual(old["status"], "superseded")
        self.assertEqual(
            next(
                row["session_generation"]
                for row in rows
                if row["character_id"] == members[1]["character"]["id"]
            ),
            members[1]["generation"],
        )
        self.assertFalse(
            resume_member(
                self.store,
                actor["account"],
                generation,
                actor["character"]["id"],
                run["instance_id"],
            )["rebound"]
        )

    def test_forged_instance_or_unselected_new_session_is_rejected(self):
        members, _ = self.party(2)
        run = self.enter(members[0])
        actor = members[0]
        with self.assertRaises(ValueError):
            resume_member(
                self.store,
                actor["account"],
                actor["generation"],
                actor["character"]["id"],
                run["instance_id"] + 1,
            )
        generation = self.store.begin_session(actor["account"], ttl=10000)
        with self.assertRaises(ValueError):
            resume_member(
                self.store,
                actor["account"],
                generation,
                actor["character"]["id"],
                run["instance_id"],
            )
