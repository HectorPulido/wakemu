import struct
import threading
from concurrent.futures import ThreadPoolExecutor
import unittest
import uuid
from unittest.mock import patch

from postgres_case import PostgresCase
from psycopg.types.json import Jsonb
from wakfu_server import party_dispatch, party_wire
from wakfu_server.world import World


class Peer:
    def __init__(self, name):
        self.name = name
        self.closed = False

    def shutdown(self, how):
        self.closed = True


class PartyDispatchTests(PostgresCase):
    def setUp(self):
        super().setUp()
        self.store.clock = lambda: 2_000_000_000.0
        self.sent = []
        self.world = World(
            lambda character: ("spawn", character["id"]),
            lambda character: ("remove", character["id"]),
            self._deliver,
        )
        self.parties = party_dispatch.Parties(self.store, self.world)

    def _deliver(self, peer, opcode, body):
        entered = getattr(peer, "delivery_entered", None)
        release = getattr(peer, "delivery_release", None)
        if entered is not None:
            entered.set()
            if not release.wait(5):
                raise TimeoutError("test delivery gate timed out")
        if getattr(peer, "fail", False):
            raise BrokenPipeError("peer disconnected")
        self.sent.append((peer.name, opcode, body))

    def player(self, label, *, map_id=1134, instance_id=0):
        account = self.store.register("pd" + uuid.uuid4().hex[:10], "test-password")[
            "id"
        ]
        letters = str.maketrans("0123456789", "abcdefghij")
        name = (label[:5] + uuid.uuid4().hex[:8]).translate(letters)
        character = self.store.create_character(account, name)
        generation = self.store.begin_session(account, ttl=10_000)
        character = self.store.select_character(account, generation, character["id"])
        character.update(map_id=map_id, instance_id=instance_id)
        peer = Peer(name)
        self.world.join(generation, peer, character)
        return {
            "account": account,
            "generation": generation,
            "character": character,
            "peer": peer,
        }

    @staticmethod
    def invite_body(target_id):
        return b"\x01" + struct.pack(">qqBq", 123, -1, 1, target_id)

    @staticmethod
    def answer_body(accepted, inviter):
        encoded = inviter["character"]["name"].encode("utf-8")
        return (
            b"\x01"
            + bytes((int(accepted), len(encoded)))
            + encoded
            + b"\x00"
            + struct.pack(">q", inviter["character"]["id"])
        )

    @staticmethod
    def member_body(party_id, member_id):
        return struct.pack(">qq", party_id, member_id)

    def request(self, player, opcode, body):
        return self.parties.handle(
            opcode,
            body,
            player["account"],
            player["generation"],
            player["character"]["id"],
        )

    def _roster_events(self):
        return [(peer, body) for peer, opcode, body in self.sent if opcode == 1184]

    def _members(self, party_id):
        with self.store.connection() as db:
            return [
                row["character_id"]
                for row in db.execute(
                    "SELECT character_id FROM player_party_members WHERE party_id=%s "
                    "ORDER BY joined_order",
                    (party_id,),
                ).fetchall()
            ]

    def _accept(self, inviter, invitee):
        self.request(inviter, 1156, self.invite_body(invitee["character"]["id"]))
        return self.request(invitee, 1031, self.answer_body(True, inviter))

    def test_native_invite_accept_publishes_roster_only_to_members_across_maps(self):
        leader = self.player("leader", map_id=1134, instance_id=2)
        member = self.player("member", map_id=527, instance_id=9)
        third = self.player("third", map_id=1134, instance_id=2)
        self.sent.clear()

        self.request(leader, 1156, self.invite_body(member["character"]["id"]))
        self.assertEqual(
            [(p, op) for p, op, _ in self.sent], [(member["peer"].name, 1072)]
        )
        self.assertEqual(
            self.sent[0][2],
            party_wire.invitation(
                leader["character"]["id"], leader["character"]["name"]
            )[1],
        )

        party_id = self.request(member, 1031, self.answer_body(True, leader))
        self.assertEqual(party_id >> 56, 1)
        roster = self._roster_events()
        self.assertEqual(
            {peer for peer, _ in roster}, {leader["peer"].name, member["peer"].name}
        )
        self.assertEqual(len(roster), 2)
        self.assertNotIn(third["peer"].name, {peer for peer, _, _ in self.sent})
        self.assertEqual(
            self._members(party_id),
            [leader["character"]["id"], member["character"]["id"]],
        )
        self.assertTrue(
            all(body[0:8] == struct.pack(">q", party_id) for _, body in roster)
        )

    def test_name_lookup_uses_canonical_identity_and_missing_target_leaves_no_invitation(
        self,
    ):
        leader = self.player("leader")
        target = self.player("target", map_id=527)
        self.sent.clear()

        def by_name(name):
            encoded = name.encode("utf-8")
            return b"\x01" + struct.pack(">qqBB", -7, -2, 0, len(encoded)) + encoded

        self.request(leader, 1156, by_name(target["character"]["name"].swapcase()))
        self.assertEqual(
            self.sent,
            [
                (
                    target["peer"].name,
                    *party_wire.invitation(
                        leader["character"]["id"], leader["character"]["name"]
                    ),
                )
            ],
        )
        with self.store.connection() as db:
            invitation = db.execute(
                "SELECT inviter_id,invitee_id,invitee_generation "
                "FROM player_party_invitations"
            ).fetchone()
        self.assertEqual(invitation["inviter_id"], leader["character"]["id"])
        self.assertEqual(invitation["invitee_id"], target["character"]["id"])
        self.assertEqual(invitation["invitee_generation"], target["generation"])
        self.request(target, 1031, self.answer_body(False, leader))
        self.sent.clear()
        for missing in ("undefined", "MissingPlayer"):
            with self.subTest(target=missing), self.assertRaisesRegex(
                ValueError, "no está conectado"
            ):
                self.request(leader, 1156, by_name(missing))
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                0,
            )
        self.assertEqual(self.sent, [])

    def test_decline_spoof_and_stale_session_do_not_publish_or_mutate_membership(self):
        leader = self.player("leader")
        target = self.player("target", map_id=527)
        impostor = self.player("fake")
        self.request(leader, 1156, self.invite_body(target["character"]["id"]))
        self.sent.clear()
        self.assertIsNone(self.request(target, 1031, self.answer_body(False, leader)))
        self.assertEqual(self._roster_events(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )

        self.request(leader, 1156, self.invite_body(target["character"]["id"]))
        self.sent.clear()
        with self.assertRaisesRegex(ValueError, "native party invitation"):
            self.request(target, 1031, self.answer_body(True, impostor))
        self.assertEqual(self._roster_events(), [])
        target["generation"] = self.store.begin_session(target["account"], ttl=10_000)
        target["character"] = self.store.select_character(
            target["account"], target["generation"], target["character"]["id"]
        )
        replacement = Peer("target-reconnected")
        target["character"].update(map_id=527, instance_id=0)
        self.world.join(target["generation"], replacement, target["character"])
        target["peer"] = replacement
        with self.assertRaisesRegex(ValueError, "native party invitation"):
            self.request(target, 1031, self.answer_body(True, leader))
        self.assertEqual(self._roster_events(), [])
        with self.store.connection() as db:
            self.assertEqual(
                db.execute("SELECT count(*) AS n FROM player_parties").fetchone()["n"],
                0,
            )

    def test_refresh_reconnect_checkpoint_health_and_effective_levels_are_current(self):
        leader, member = self.player("leader"), self.player("member", map_id=527)
        party_id = self._accept(leader, member)
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=0,hp_damage=max_hp,health_dead=true WHERE id=%s",
                (member["character"]["id"],),
            )
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants VALUES(%s,%s,%s,0)",
                (fight_id, leader["character"]["id"], leader["account"]),
            )
            db.execute(
                "INSERT INTO fight_checkpoints VALUES(%s,%s,%s,1,'active',%s,%s)",
                (
                    fight_id,
                    leader["account"],
                    leader["generation"],
                    Jsonb(
                        {
                            "actors": {
                                str(leader["character"]["id"]): {
                                    "hp": 17,
                                    "max_hp": 41,
                                    "effective_level": 23,
                                }
                            }
                        }
                    ),
                    self.store.now(),
                ),
            )
        self.sent.clear()
        # Refresh after peer replacement exercises reconnect replay from durable membership.
        leader["generation"] = self.store.begin_session(leader["account"], ttl=10_000)
        leader["character"] = self.store.select_character(
            leader["account"], leader["generation"], leader["character"]["id"]
        )
        peer = Peer("leader-new")
        leader["character"].update(map_id=1134, instance_id=0)
        self.world.join(leader["generation"], peer, leader["character"])
        leader["peer"] = peer
        self.sent.clear()
        self.assertTrue(
            self.parties.refresh(
                leader["account"], leader["generation"], leader["character"]["id"]
            )
        )
        packets = [
            body
            for name, opcode, body in self.sent
            if name == peer.name and opcode == 1184
        ]
        self.assertEqual(len(packets), 1)
        parsed = self._decode_roster(packets[0])
        rows = {row["id"]: row for row in parsed}
        self.assertEqual(rows[leader["character"]["id"]]["effective_level"], 23)
        self.assertEqual(
            (
                rows[leader["character"]["id"]]["hp"],
                rows[leader["character"]["id"]]["max_hp"],
                rows[leader["character"]["id"]]["in_fight"],
            ),
            (17, 41, True),
        )
        self.assertTrue(rows[member["character"]["id"]]["dead"])
        self.assertEqual(
            self._members(party_id),
            [leader["character"]["id"], member["character"]["id"]],
        )

    def test_leader_transfer_kick_and_self_leave_publish_removal_and_latest_leader(
        self,
    ):
        leader, member, third = (
            self.player("lead"),
            self.player("member", map_id=527),
            self.player("third", map_id=22),
        )
        party_id = self._accept(leader, member)
        self._accept(leader, third)
        self.sent.clear()
        self.request(
            leader, 1066, self.member_body(party_id, member["character"]["id"])
        )
        self.assertEqual(
            self._members(party_id),
            [
                leader["character"]["id"],
                member["character"]["id"],
                third["character"]["id"],
            ],
        )
        self.assertEqual(
            {peer for peer, _ in self._roster_events()},
            {p["peer"].name for p in (leader, member, third)},
        )

        self.sent.clear()
        self.request(member, 1074, self.member_body(party_id, third["character"]["id"]))
        self.assertEqual(
            self._members(party_id),
            [leader["character"]["id"], member["character"]["id"]],
        )
        with self.store.connection() as db:
            two_member_party = db.execute(
                "SELECT leader_id FROM player_parties WHERE id=%s", (party_id,)
            ).fetchone()
        self.assertEqual(two_member_party["leader_id"], member["character"]["id"])
        removed = [(peer, body) for peer, opcode, body in self.sent if opcode == 1049]
        self.assertEqual(
            {peer for peer, _ in removed},
            {p["peer"].name for p in (leader, member, third)},
        )
        self.assertTrue(
            all(
                body == party_wire.removed(party_id, [third["character"]["id"]])[1]
                for _, body in removed
            )
        )

        self.sent.clear()
        self.request(
            leader, 1074, self.member_body(party_id, leader["character"]["id"])
        )
        with self.store.connection() as db:
            self.assertIsNone(
                db.execute(
                    "SELECT id FROM player_parties WHERE id=%s", (party_id,)
                ).fetchone()
            )
        singleton_removals = [
            (peer, body) for peer, opcode, body in self.sent if opcode == 1049
        ]
        self.assertEqual(
            {peer for peer, _ in singleton_removals},
            {leader["peer"].name, member["peer"].name},
        )
        expected_removed = party_wire.removed(
            party_id, [leader["character"]["id"], member["character"]["id"]]
        )[1]
        self.assertTrue(all(body == expected_removed for _, body in singleton_removals))
        self.assertEqual(self._roster_events(), [])

    def test_six_member_cap_is_enforced_through_native_dispatch(self):
        people = [self.player(f"p{i}", map_id=i * 10) for i in range(7)]
        leader = people[0]
        for invitee in people[1:6]:
            self._accept(leader, invitee)
        party_body = self._roster_events()[0][1]
        party_id = struct.unpack_from(">q", party_body)[0]
        self.assertEqual(len(self._members(party_id)), 6)
        seventh = people[6]
        self.sent.clear()
        with self.assertRaisesRegex(ValueError, "full"):
            self.request(leader, 1156, self.invite_body(seventh["character"]["id"]))
        self.assertEqual(len(self._members(party_id)), 6)
        self.assertEqual(self.sent, [])

    def test_invitation_delivery_failure_is_reported_without_roster_publication(self):
        leader, target = self.player("leader"), self.player("target")
        target["peer"].fail = True
        with self.assertRaisesRegex(ValueError, "entregar"):
            self.request(leader, 1156, self.invite_body(target["character"]["id"]))
        self.assertTrue(target["peer"].closed)
        self.assertEqual(self._roster_events(), [])
        # The durable invitation currently remains pending after the failed send.
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                0,
            )

    def test_roster_delivery_failure_keeps_committed_membership_and_reaches_other_members(
        self,
    ):
        leader, target = self.player("leader"), self.player("target", map_id=527)
        self.request(leader, 1156, self.invite_body(target["character"]["id"]))
        target["peer"].fail = True
        self.sent.clear()

        party_id = self.request(target, 1031, self.answer_body(True, leader))

        self.assertEqual(
            self._members(party_id),
            [leader["character"]["id"], target["character"]["id"]],
        )
        self.assertTrue(target["peer"].closed)
        self.assertEqual(
            {peer for peer, _ in self._roster_events()}, {leader["peer"].name}
        )
        with self.store.connection() as db:
            self.assertEqual(
                db.execute(
                    "SELECT count(*) AS n FROM player_party_invitations"
                ).fetchone()["n"],
                0,
            )

    def test_refresh_online_repairs_a_missed_roster_and_reloads_current_health(self):
        leader, member = self.player("leader"), self.player("member", map_id=527)
        party_id = self._accept(leader, member)
        old_peer = member["peer"]
        old_peer.fail = True
        with self.store.connection() as db:
            db.execute(
                "UPDATE characters SET hp=hp-3 WHERE id=%s",
                (member["character"]["id"],),
            )
        self.sent.clear()
        self.parties.refresh_online()
        self.assertTrue(old_peer.closed)
        self.assertEqual(
            {peer for peer, _ in self._roster_events()}, {leader["peer"].name}
        )

        # Reconnect with the current lease and ask the periodic repair pass to
        # replay the durable roster, including the changed persistent HP.
        member["generation"] = self.store.begin_session(member["account"], ttl=10_000)
        member["character"] = self.store.select_character(
            member["account"], member["generation"], member["character"]["id"]
        )
        replacement = Peer("member-reconnected")
        member["character"].update(map_id=527, instance_id=0)
        self.world.join(member["generation"], replacement, member["character"])
        member["peer"] = replacement
        self.sent.clear()
        self.parties.refresh_online()
        packet = next(
            body
            for peer, opcode, body in self.sent
            if peer == replacement.name and opcode == 1184
        )
        rows = self._decode_roster(packet)
        current = next(row for row in rows if row["id"] == member["character"]["id"])
        with self.store.connection() as db:
            hp = db.execute(
                "SELECT hp FROM characters WHERE id=%s", (member["character"]["id"],)
            ).fetchone()["hp"]
        self.assertEqual(current["hp"], hp)
        self.assertEqual(
            self._members(party_id),
            [leader["character"]["id"], member["character"]["id"]],
        )

    def test_active_fight_without_checkpoint_never_publishes_persistent_hp_as_current(
        self,
    ):
        leader, member = self.player("leader"), self.player("member")
        party_id = self._accept(leader, member)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants VALUES(%s,%s,%s,0)",
                (fight_id, leader["character"]["id"], leader["account"]),
            )
        self.sent.clear()
        with self.assertRaises(party_dispatch.PartySnapshotUnavailable) as raised:
            self.parties.refresh(
                leader["account"], leader["generation"], leader["character"]["id"]
            )
        self.assertEqual(
            raised.exception.diagnostic(),
            dict(
                party_id=party_id,
                character_id=leader["character"]["id"],
                fight_id=fight_id,
            ),
        )
        self.assertEqual(self._roster_events(), [])

    def test_refresh_online_defers_only_party_with_missing_fight_snapshot(self):
        blocked_leader, blocked_member = self.player("blocked"), self.player("blockm")
        blocked_party = self._accept(blocked_leader, blocked_member)
        healthy_leader, healthy_member = self.player("healthy", map_id=81), self.player(
            "healthym", map_id=999
        )
        healthy_party = self._accept(healthy_leader, healthy_member)
        with self.store.connection() as db:
            fight_id = db.execute(
                "INSERT INTO combat_fights(status) VALUES('active') RETURNING id"
            ).fetchone()["id"]
            db.execute(
                "INSERT INTO combat_fight_participants VALUES(%s,%s,%s,0)",
                (
                    fight_id,
                    blocked_member["character"]["id"],
                    blocked_member["account"],
                ),
            )

        self.sent.clear()
        result = self.parties.refresh_online()

        self.assertEqual(result["refreshed"], 1)
        self.assertEqual(
            result["deferred"],
            [
                dict(
                    party_id=blocked_party,
                    character_id=blocked_member["character"]["id"],
                    fight_id=fight_id,
                )
            ],
        )
        published = {peer for peer, _ in self._roster_events()}
        self.assertEqual(
            published,
            {healthy_leader["peer"].name, healthy_member["peer"].name},
        )
        self.assertNotIn(blocked_leader["peer"].name, published)
        self.assertNotIn(blocked_member["peer"].name, published)
        self.assertEqual(healthy_party >> 56, 1)

    def test_refresh_online_propagates_unrelated_publication_errors(self):
        leader, member = self.player("raise"), self.player("raisem")
        self._accept(leader, member)
        with self.assertRaisesRegex(RuntimeError, "publication storage failure"):
            with patch.object(
                self.parties,
                "_publish",
                side_effect=RuntimeError("publication storage failure"),
            ):
                self.parties.refresh_online()

    def test_blocked_peer_does_not_hold_world_lock_or_block_an_unrelated_party(self):
        leader_a, member_a = self.player("alpha"), self.player("alpham", map_id=527)
        leader_b, member_b = self.player("bravo", map_id=81), self.player(
            "bravom", map_id=999
        )
        self._accept(leader_a, member_a)
        self._accept(leader_b, member_b)
        stripe_a = hash(self.parties._key(leader_a["character"]["id"])) % len(
            self.parties.locks
        )
        stripe_b = hash(self.parties._key(leader_b["character"]["id"])) % len(
            self.parties.locks
        )
        self.assertNotEqual(
            stripe_a, stripe_b, "test requires independent party stripes"
        )

        entered, release = threading.Event(), threading.Event()
        leader_a["peer"].delivery_entered = entered
        leader_a["peer"].delivery_release = release
        try:
            with ThreadPoolExecutor(max_workers=2) as pool:
                blocked = pool.submit(
                    self.parties.refresh,
                    leader_a["account"],
                    leader_a["generation"],
                    leader_a["character"]["id"],
                )
                self.assertTrue(entered.wait(3), "party A never reached its peer write")
                # This world read takes the world membership lock, while the
                # first thread is stalled inside the socket-delivery callback.
                self.assertEqual(len(self.world.snapshot()), 4)
                independent = pool.submit(
                    self.parties.refresh,
                    leader_b["account"],
                    leader_b["generation"],
                    leader_b["character"]["id"],
                )
                self.assertTrue(independent.result(timeout=3))
                release.set()
                self.assertTrue(blocked.result(timeout=3))
        finally:
            release.set()

    @staticmethod
    def _decode_roster(body):
        group_id, _kind, _reserved, leader_id, count = struct.unpack_from(
            ">qBhqh", body
        )
        offset = struct.calcsize(">qBhqh")
        output = []
        for _ in range(count):
            identity, size = struct.unpack_from(">qh", body, offset)
            record = body[offset + 10 : offset + 10 + size]
            offset += 10 + size
            directories = {
                record[1 + i * 5]: struct.unpack_from(">i", record, 2 + i * 5)[0]
                for i in range(record[0])
            }

            def section(tag):
                start = directories[tag]
                end = min(
                    (value for value in directories.values() if value > start),
                    default=len(record),
                )
                return record[start + 1 : end]

            effective = struct.unpack(">h", section(3))[0]
            hp, maximum, _, _ = struct.unpack(">iiii", section(5))
            output.append(
                {
                    "id": identity,
                    "effective_level": effective,
                    "hp": hp,
                    "max_hp": maximum,
                    "dead": struct.unpack(">?", section(2))[0],
                    "in_fight": struct.unpack(">?", section(1))[0],
                }
            )
        if (
            offset != len(body)
            or leader_id not in {row["id"] for row in output}
            or group_id >> 56 != 1
        ):
            raise AssertionError("Malformed party roster sent by dispatcher")
        return output


if __name__ == "__main__":
    unittest.main()
