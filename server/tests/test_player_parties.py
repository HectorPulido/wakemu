from concurrent.futures import ThreadPoolExecutor
import threading
import uuid
import struct

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb

from wakfu_server import player_parties
from wakfu_server.party_wire import invitation as encode_invitation
from wakfu_server.party_wire import invitation_answer


class PlayerPartyTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.now = 2_000_000_000.0
        self.store.clock = lambda: self.now

    def player(self, label):
        account = self.store.register(f"p{uuid.uuid4().hex[:10]}", "test-password")[
            "id"
        ]
        letters = str.maketrans("0123456789", "abcdefghij")
        character_name = "Hero" + uuid.uuid4().hex[:8].translate(letters)
        character = self.store.create_character(account, character_name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        return {"account": account, "generation": generation, "character": character}

    def invite(self, inviter, invitee):
        return player_parties.invite(
            self.store,
            inviter["account"],
            inviter["generation"],
            inviter["character"]["id"],
            invitee["character"]["id"],
        )

    def answer(self, invitee, token, accepted=True):
        return player_parties.answer(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            token,
            accepted,
        )

    @staticmethod
    def native_answer(accepted, first_name, inviter_id, second_name=""):
        first = first_name.encode("utf-8")
        second = second_name.encode("utf-8")
        body = (
            b"\x01"
            + bytes((int(accepted), len(first)))
            + first
            + bytes((len(second),))
            + second
            + struct.pack(">q", inviter_id)
        )
        return invitation_answer(body)

    def answer_wire(self, invitee, request):
        return player_parties.answer_native(
            self.store,
            invitee["account"],
            invitee["generation"],
            invitee["character"]["id"],
            request,
        )

    def test_invite_and_answer_reject_self_offline_stale_foreign_and_bad_types(self):
        leader = self.player("leader")
        target = self.player("target")
        offline = self.player("offline")
        self.store.begin_session(
            offline["account"]
        )  # selected character lease is replaced

        with self.assertRaisesRegex(ValueError, "yourself"):
            player_parties.invite(
                self.store,
                leader["account"],
                leader["generation"],
                leader["character"]["id"],
                leader["character"]["id"],
            )
        with self.assertRaisesRegex(ValueError, "offline"):
            self.invite(leader, offline)
        with self.assertRaises(ValueError):
            player_parties.invite(
                self.store,
                leader["account"],
                "stale-generation",
                leader["character"]["id"],
                target["character"]["id"],
            )
        with self.assertRaises(ValueError):
            player_parties.invite(
                self.store,
                target["account"],
                leader["generation"],
                leader["character"]["id"],
                target["character"]["id"],
            )
        with self.assertRaises(ValueError):
            player_parties.invite(
                self.store,
                leader["account"],
                leader["generation"],
                leader["character"]["id"],
                True,
            )

        token = self.invite(leader, target)
        with self.assertRaisesRegex(ValueError, "owned"):
            self.answer(leader, token)
        with self.assertRaisesRegex(ValueError, "token"):
            self.answer(target, "not-a-uuid")
        with self.assertRaisesRegex(ValueError, "answer"):
            self.answer(target, token, 1)
        with self.assertRaisesRegex(ValueError, "owned"):
            player_parties.answer(
                self.store,
                target["account"],
                target["generation"],
                target["character"]["id"],
                uuid.uuid4(),
                True,
            )

    def test_expired_stale_invitee_and_refused_invites_do_not_create_membership(self):
        leader = self.player("expiration-leader")
        target = self.player("expiration-target")

        expired = self.invite(leader, target)
        self.now += 61
        with self.assertRaisesRegex(ValueError, "expired or stale"):
            self.answer(target, expired)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )

        # Restore time to a live invitation window; replacing either generation
        # invalidates the invitation even while both accounts remain connected.
        self.now -= 60
        stale = self.invite(leader, target)
        target["generation"] = self.store.begin_session(target["account"], ttl=10_000)
        with self.assertRaises(ValueError):
            self.answer(target, stale)

        fresh_target = self.player("refusal-target")
        refused = self.invite(leader, fresh_target)
        self.assertIsNone(self.answer(fresh_target, refused, False))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                1,
            )

    def test_accept_creates_one_party_and_two_members_and_replay_cannot_duplicate(self):
        leader = self.player("accept-leader")
        target = self.player("accept-target")
        token = self.invite(leader, target)
        party_id = self.answer(target, token)
        self.assertEqual(party_id >> 56, 1)
        with self.store.connection() as db:
            party = db.execute(
                "SELECT * FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()
            members = db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY joined_order",
                (party_id,),
            ).fetchall()
        self.assertEqual(party["leader_id"], leader["character"]["id"])
        self.assertEqual(
            [row["character_id"] for row in members],
            [leader["character"]["id"], target["character"]["id"]],
        )
        with self.assertRaisesRegex(ValueError, "Unknown owned"):
            self.answer(target, token)
        reopened = self.reopen()
        with reopened.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                2,
            )

    def test_og_invitation_and_ow_accept_bind_character_id_name_and_ticket(self):
        leader, target = self.player("wire-leader"), self.player("wire-target")
        token = self.invite(leader, target)
        outgoing = encode_invitation(
            leader["character"]["id"], leader["character"]["name"]
        )
        self.assertEqual(outgoing[0], 1072)
        self.assertEqual(outgoing[1][-8:], struct.pack(">q", leader["character"]["id"]))
        request = self.native_answer(
            True, leader["character"]["name"], leader["character"]["id"]
        )
        party_id = self.answer_wire(target, request)
        self.assertEqual(party_id >> 56, 1)
        with self.assertRaisesRegex(ValueError, "owned"):
            self.answer_wire(target, request)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                0,
            )

    def test_ow_reject_and_spoofed_contexts_leave_membership_unchanged(self):
        leader, target, impostor = (
            self.player("wire-reject-leader"),
            self.player("wire-reject-target"),
            self.player("wire-reject-impostor"),
        )
        self.invite(leader, target)
        valid = self.native_answer(
            False, leader["character"]["name"], leader["character"]["id"]
        )
        self.assertIsNone(self.answer_wire(target, valid))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                0,
            )

        target2 = self.player("wire-spoof-target")
        token = self.invite(leader, target2)
        forged_requests = (
            self.native_answer(
                True, leader["character"]["name"], impostor["character"]["id"]
            ),
            self.native_answer(
                True, impostor["character"]["name"], leader["character"]["id"]
            ),
            self.native_answer(
                True, leader["character"]["name"], leader["character"]["id"], "NotEmpty"
            ),
        )
        for request in forged_requests:
            with self.subTest(request=request), self.assertRaisesRegex(
                ValueError, "native party invitation"
            ):
                self.answer_wire(target2, request)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(token),),
                ).fetchone()["n"],
                1,
            )
        accepted = self.native_answer(
            True, leader["character"]["name"], leader["character"]["id"]
        )
        self.answer_wire(target2, accepted)

    def test_ow_stale_generation_and_expired_ticket_do_not_create_party(self):
        leader, target = self.player("wire-stale-leader"), self.player(
            "wire-stale-target"
        )
        self.invite(leader, target)
        stale = self.native_answer(
            True, leader["character"]["name"], leader["character"]["id"]
        )
        target["generation"] = self.store.begin_session(target["account"], ttl=10_000)
        target["character"] = self.store.select_character(
            target["account"], target["generation"], target["character"]["id"]
        )
        with self.assertRaisesRegex(ValueError, "native party invitation"):
            self.answer_wire(target, stale)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )

        fresh_target = self.player("wire-expired-target")
        self.invite(leader, fresh_target)
        expired = self.native_answer(
            True, leader["character"]["name"], leader["character"]["id"]
        )
        self.now += 61
        with self.assertRaisesRegex(ValueError, "native party invitation"):
            self.answer_wire(fresh_target, expired)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                0,
            )

    def test_only_party_leader_can_invite_and_policy_failure_rolls_back(self):
        leader, member, guest = (self.player(f"roles-{i}") for i in range(3))
        self.answer(member, self.invite(leader, member))
        token = self.invite(leader, guest)
        with self.assertRaisesRegex(ValueError, "Only the party leader"):
            self.invite(member, self.player("roles-target"))
        with self.assertRaisesRegex(ValueError, "party member"):
            player_parties.invite(
                self.store,
                leader["account"],
                leader["generation"],
                leader["character"]["id"],
                "not-an-integer-id",
            )
        policy_guest = self.player("policy-version-target")
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='player_party_policy'",
                (Jsonb({"version": True, "max_members": 6, "invitation_seconds": 60}),),
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            self.invite(leader, policy_guest)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE invitee_id=%s",
                    (policy_guest["character"]["id"],),
                ).fetchone()["n"],
                0,
            )
        with self.store.connection() as db:
            db.execute(
                "UPDATE settings SET value=%s WHERE name='player_party_policy'",
                (Jsonb({"version": 1, "max_members": True, "invitation_seconds": 60}),),
            )
        with self.assertRaisesRegex(ValueError, "policy"):
            self.answer(guest, token)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                1,
            )

    def test_reconnect_snapshot_keeps_offline_members_and_requires_owned_lease(self):
        leader, member, outsider = (
            self.player("snapshot-0"),
            self.player("snapshot-1"),
            self.player("snapshot-2"),
        )
        party_id = self.answer(member, self.invite(leader, member))
        # Going offline does not dissolve membership; snapshots are authoritative
        # party state, not a list filtered by currently connected sessions.
        member["generation"] = self.store.begin_session(member["account"], ttl=10_000)
        snapshot = player_parties.snapshot(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
        )
        self.assertEqual(
            (snapshot["party_id"], snapshot["leader_id"], snapshot["revision"]),
            (party_id, leader["character"]["id"], 2),
        )
        rows = {row["id"]: row for row in snapshot["members"]}
        self.assertEqual(
            set(rows), {leader["character"]["id"], member["character"]["id"]}
        )
        self.assertEqual(
            rows[member["character"]["id"]]["account_id"], member["account"]
        )
        self.assertIn("hp", rows[member["character"]["id"]])
        self.assertIn("max_hp", rows[member["character"]["id"]])
        self.assertIsNone(
            player_parties.snapshot(
                self.store,
                outsider["account"],
                outsider["generation"],
                outsider["character"]["id"],
            )
        )
        with self.assertRaises(ValueError):
            player_parties.snapshot(
                self.store,
                leader["account"],
                "wrong-generation",
                leader["character"]["id"],
            )
        reopened = self.reopen()
        restored = player_parties.snapshot(
            reopened, leader["account"], leader["generation"], leader["character"]["id"]
        )
        self.assertEqual(restored["party_id"], party_id)
        self.assertEqual({row["id"] for row in restored["members"]}, set(rows))

    def test_expiry_cleanup_is_bounded_skips_locked_ticket_and_keeps_new_ticket(self):
        leader, target, second_target, fresh_target = (
            self.player("expire-0"),
            self.player("expire-1"),
            self.player("expire-2"),
            self.player("expire-3"),
        )
        token = self.invite(leader, target)
        old_token = self.invite(leader, second_target)
        self.now += 61
        fresh_token = self.invite(leader, fresh_target)
        with self.store.connection() as db:
            db.execute(
                "SELECT token FROM player_party_invitations WHERE token=%s FOR UPDATE",
                (uuid.UUID(token),),
            )
            # Both old invitations are due. The cleanup deletes one free row
            # and skips the other row locked by this transaction.
            self.assertEqual(player_parties.expire(self.store, limit=1), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(old_token),),
                ).fetchone()["n"],
                0,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(token),),
                ).fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(fresh_token),),
                ).fetchone()["n"],
                1,
            )
        with self.assertRaisesRegex(ValueError, "expired or stale"):
            self.answer(target, token)
        self.assertEqual(player_parties.expire(self.store, limit=1), 1)
        self.assertEqual(player_parties.expire(self.store, limit=1), 0)
        for limit in (True, 0, 1025):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                player_parties.expire(self.store, limit=limit)

    def test_expiry_sweep_does_not_consume_concurrent_live_answer(self):
        leader, target = self.player("live-answer-leader"), self.player(
            "live-answer-target"
        )
        token = self.invite(leader, target)
        answer_started = threading.Event()

        def accept_locked_ticket():
            answer_started.set()
            return self.answer(target, token)

        with ThreadPoolExecutor(max_workers=1) as executor:
            with self.store.connection() as db:
                db.execute(
                    "SELECT token FROM player_party_invitations WHERE token=%s FOR UPDATE",
                    (uuid.UUID(token),),
                )
                answer_future = executor.submit(accept_locked_ticket)
                self.assertTrue(answer_started.wait(timeout=5))
                # The ticket is still live, so cleanup leaves it alone while
                # answer is waiting on the transaction's row lock.
                self.assertEqual(player_parties.expire(self.store, limit=1), 0)
            party_id = answer_future.result(timeout=10)
        self.assertEqual(party_id >> 56, 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(token),),
                ).fetchone()["n"],
                0,
            )

    def test_two_simultaneous_accepts_cannot_exceed_six_member_policy(self):
        leader = self.player("capacity-leader")
        existing = [self.player(f"capacity-existing-{i}") for i in range(4)]
        for member in existing:
            self.answer(member, self.invite(leader, member))
        contenders = [self.player(f"capacity-racer-{i}") for i in range(2)]
        tokens = [self.invite(leader, member) for member in contenders]
        barrier = threading.Barrier(2)

        def accept(pair):
            member, token = pair
            barrier.wait(timeout=5)
            try:
                return self.answer(member, token)
            except ValueError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(accept, zip(contenders, tokens)))
        self.assertEqual(
            sum(not isinstance(value, ValueError) for value in outcomes), 1
        )
        self.assertEqual(sum(isinstance(value, ValueError) for value in outcomes), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                6,
            )

    def test_competing_invites_to_same_recipient_create_exactly_one_membership(self):
        first, second, target = (self.player(f"competition-{i}") for i in range(3))
        tokens = [self.invite(first, target), self.invite(second, target)]
        barrier = threading.Barrier(2)

        def accept(pair):
            leader, token = pair
            barrier.wait(timeout=5)
            try:
                return self.answer(target, token)
            except ValueError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(accept, zip((first, second), tokens)))
        self.assertEqual(
            sum(not isinstance(value, ValueError) for value in outcomes), 1
        )
        self.assertEqual(sum(isinstance(value, ValueError) for value in outcomes), 1)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                1,
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                0,
            )

    def test_leave_transfer_kick_oldest_successor_and_last_member_cleanup(self):
        leader, first, second, outsider = (
            self.player(f"membership-{i}") for i in range(4)
        )
        party_id = self.answer(first, self.invite(leader, first))
        self.assertEqual(self.answer(second, self.invite(leader, second)), party_id)
        token_from_old_leader = self.invite(leader, outsider)

        with self.assertRaisesRegex(ValueError, "Only the party leader"):
            player_parties.change_member(
                self.store,
                first["account"],
                first["generation"],
                first["character"]["id"],
                party_id,
                second["character"]["id"],
            )

        # Explicit leadership transfer retains members, advances revision, and
        # cancels pending invitations issued by the former leader.
        before_revision = self.store.connection
        with self.store.connection() as db:
            revision = db.execute(
                "SELECT revision FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()["revision"]
        transferred = player_parties.change_member(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            party_id,
            first["character"]["id"],
            transfer=True,
        )
        self.assertEqual(transferred["leader_id"], first["character"]["id"])
        self.assertEqual(transferred["removed"], [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT revision FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()["revision"],
                revision + 1,
            )
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(token_from_old_leader),),
                ).fetchone()
            )

        # Removing one of three retains a two-member party. Then the former
        # leader leaves the two-member party, which must dissolve rather than
        # strand its sole survivor in an unusable singleton.
        kicked = player_parties.change_member(
            self.store,
            first["account"],
            first["generation"],
            first["character"]["id"],
            party_id,
            second["character"]["id"],
        )
        self.assertEqual(kicked["removed"], [second["character"]["id"]])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_members WHERE party_id=%s",
                    (party_id,),
                ).fetchone()["n"],
                2,
            )
            self.assertEqual(
                db.execute(
                    "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()["leader_id"],
                first["character"]["id"],
            )
        left = player_parties.change_member(
            self.store,
            leader["account"],
            leader["generation"],
            leader["character"]["id"],
            party_id,
            leader["character"]["id"],
        )
        self.assertIsNone(left["leader_id"])
        self.assertEqual(
            set(left["removed"]), {leader["character"]["id"], first["character"]["id"]}
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT 1 FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()
            )
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_party_members").fetchone()[
                    "n"
                ],
                0,
            )

    def test_concurrent_invitation_accept_and_inviter_leave_has_no_dangling_party(self):
        leader = self.player("leave-race-leader")
        first, target = self.player("leave-race-first"), self.player(
            "leave-race-target"
        )
        party_id = self.answer(first, self.invite(leader, first))
        token = self.invite(leader, target)
        barrier = threading.Barrier(2)

        def accept():
            barrier.wait(timeout=5)
            try:
                return self.answer(target, token)
            except ValueError as error:
                return error

        def leave():
            barrier.wait(timeout=5)
            try:
                return player_parties.change_member(
                    self.store,
                    leader["account"],
                    leader["generation"],
                    leader["character"]["id"],
                    party_id,
                    leader["character"]["id"],
                )
            except ValueError as error:
                return error

        with ThreadPoolExecutor(max_workers=2) as executor:
            answer_future = executor.submit(accept)
            leave_future = executor.submit(leave)
            answer_result = answer_future.result(timeout=10)
            leave_result = leave_future.result(timeout=10)
        self.assertFalse(isinstance(leave_result, ValueError))

        with self.store.connection() as db:
            party = db.execute(
                "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()
            members = db.execute(
                "SELECT character_id FROM player_party_members WHERE party_id=%s ORDER BY joined_order",
                (party_id,),
            ).fetchall()
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations WHERE token=%s",
                    (uuid.UUID(token),),
                ).fetchone()["n"],
                0,
            )
        member_ids = {row["character_id"] for row in members}
        if party is None:
            # Leave serialized before acceptance and canceled the old leader's
            # ticket, so no orphan invitation or singleton remains.
            self.assertEqual(member_ids, set())
        else:
            self.assertEqual(party["leader_id"], first["character"]["id"])
            self.assertEqual(
                member_ids, {first["character"]["id"], target["character"]["id"]}
            )
        self.assertLessEqual(len(member_ids), 2)
        self.assertNotIn(leader["character"]["id"], member_ids)
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                0,
            )
