import uuid
from datetime import datetime, timedelta, timezone

from postgres_case import PostgresCase
from psycopg.errors import CheckViolation, ForeignKeyViolation, UniqueViolation


class PlayerPartyMigrationTests(PostgresCase):
    def setUp(self):
        super().setUp()
        suffix = uuid.uuid4().hex[:10]
        self.account = self.store.register("party-schema-" + suffix, "test-password")[
            "id"
        ]
        self.leader = self.store.create_character(self.account, "Party Leader")
        self.member = self.store.create_character(self.account, "Party Member")
        self.other_leader = self.store.create_character(self.account, "Other Leader")

    def test_party_identity_starts_in_party_namespace_and_leader_fk_is_deferred(self):
        with self.store.connection() as db:
            party_id = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (self.leader["id"],),
            ).fetchone()["id"]
            self.assertGreaterEqual(party_id >> 56, 1)
            self.assertEqual(party_id >> 56, 1)
            # Parent is inserted before its required leader membership. The
            # composite FK is deferred until this transaction commits.
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (self.leader["id"], party_id),
            )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()["leader_id"],
                self.leader["id"],
            )

    def test_party_without_leader_membership_fails_deferred_fk_at_commit(self):
        with self.assertRaises(ForeignKeyViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO player_parties(leader_id) VALUES(%s)",
                    (self.leader["id"],),
                )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )

    def test_character_can_belong_to_only_one_party(self):
        with self.store.connection() as db:
            first = db.execute(
                "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                (self.leader["id"],),
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (self.leader["id"], first),
            )
            db.execute(
                "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                (self.member["id"], first),
            )
        with self.assertRaises(UniqueViolation):
            with self.store.connection() as db:
                second = db.execute(
                    "INSERT INTO player_parties(leader_id) VALUES(%s) RETURNING id",
                    (self.other_leader["id"],),
                ).fetchone()["id"]
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (self.other_leader["id"], second),
                )
                db.execute(
                    "INSERT INTO player_party_members(character_id,party_id) VALUES(%s,%s)",
                    (self.member["id"], second),
                )

    def test_invitation_expiry_is_timestamptz_indexed_and_rows_keep_expiry(self):
        with self.store.connection() as db:
            column = db.execute(
                "SELECT data_type FROM information_schema.columns "
                "WHERE table_schema=current_schema() AND table_name='player_party_invitations' "
                "AND column_name='expires_at'"
            ).fetchone()
            self.assertEqual(column["data_type"], "timestamp with time zone")
            index = db.execute(
                "SELECT indexdef FROM pg_indexes WHERE schemaname=current_schema() "
                "AND tablename='player_party_invitations' AND indexname='player_party_invitation_expiry'"
            ).fetchone()
            self.assertIsNotNone(index)
            self.assertIn("(expires_at)", index["indexdef"])

            expired_at = datetime.now(timezone.utc) - timedelta(seconds=1)
            token = uuid.uuid4()
            db.execute(
                "INSERT INTO player_party_invitations(token,inviter_id,invitee_id,"
                "inviter_generation,invitee_generation,expires_at) VALUES(%s,%s,%s,%s,%s,%s)",
                (token, self.leader["id"], self.member["id"], "g1", "g2", expired_at),
            )
            saved = db.execute(
                "SELECT expires_at FROM player_party_invitations WHERE token=%s",
                (token,),
            ).fetchone()["expires_at"]
            self.assertEqual(saved, expired_at)
            self.assertLess(saved, datetime.now(timezone.utc))

    def test_invitation_checks_distinct_characters_and_unique_pair(self):
        values = (
            uuid.uuid4(),
            self.leader["id"],
            self.member["id"],
            "g1",
            "g2",
            datetime.now(timezone.utc) + timedelta(minutes=1),
        )
        with self.store.connection() as db:
            db.execute(
                "INSERT INTO player_party_invitations(token,inviter_id,invitee_id,"
                "inviter_generation,invitee_generation,expires_at) VALUES(%s,%s,%s,%s,%s,%s)",
                values,
            )
        with self.assertRaises(UniqueViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO player_party_invitations(token,inviter_id,invitee_id,"
                    "inviter_generation,invitee_generation,expires_at) VALUES(%s,%s,%s,%s,%s,%s)",
                    (uuid.uuid4(), *values[1:]),
                )
        with self.assertRaises(CheckViolation):
            with self.store.connection() as db:
                db.execute(
                    "INSERT INTO player_party_invitations(token,inviter_id,invitee_id,"
                    "inviter_generation,invitee_generation,expires_at) VALUES(%s,%s,%s,%s,%s,%s)",
                    (
                        uuid.uuid4(),
                        self.leader["id"],
                        self.leader["id"],
                        "g1",
                        "g2",
                        values[-1],
                    ),
                )
